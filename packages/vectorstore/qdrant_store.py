import uuid
from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document as LCDocument
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    Fusion,
    FusionQuery,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from packages.code.logger import get_logger
from packages.code.models import Document, ScoredChunk
from packages.rag.sparse import SparseEmbedder

logger = get_logger(__name__)

# 하이브리드 컬렉션에서의 named vector 이름
DENSE_NAME = "dense"
SPARSE_NAME = "sparse"

# Qdrant HTTP payload 한도(기본 32MiB) 회피용. 대형 PDF에서 1k+ 청크가
# 한 번에 업로드되면 한도 초과로 400. 256은 dense+sparse+payload 합산 ~8MB 수준.
UPSERT_BATCH_SIZE = 256

# 임베딩·PointStruct 동시 메모리 점유 캡. 한 번에 모든 청크를 임베딩하면
# 큰 문서(수천 청크)에서 RAM이 GB 단위로 폭발해 시스템이 멈춘 사례 발생.
# 64청크 단위로 임베딩→upsert→폐기를 반복해 메모리 상한을 둔다.
EMBED_BATCH_SIZE = 64


class CollectionDimensionMismatch(RuntimeError):
    """기존 컬렉션 차원·구조가 현재 설정과 불일치."""


class QdrantDocumentStore:
    def __init__(
        self,
        url: str,
        collection: str,
        embeddings: Embeddings,
        search_mode: str = "vector",
        sparse_embedder: Optional[SparseEmbedder] = None,
    ):
        self._client = QdrantClient(url=url)
        self._collection = collection
        self._embeddings = embeddings
        self._dim = int(getattr(embeddings, "embedding_dim", 1536))
        self._search_mode = search_mode
        self._sparse = sparse_embedder if search_mode == "hybrid" else None

        self._ensure_collection()
        self._ensure_payload_indexes()

        # vector 모드만 기존 langchain_qdrant 재사용 (scroll·기본 삭제 등)
        # hybrid 모드는 raw Qdrant SDK로 직접 처리
        if search_mode == "vector":
            self._store = QdrantVectorStore(
                client=self._client,
                collection_name=collection,
                embedding=embeddings,
            )
        else:
            self._store = None

    # ─────────────────────────────────────────────────────
    # 컬렉션 생성·검증
    # ─────────────────────────────────────────────────────

    def _is_hybrid_collection(self, info) -> bool:
        """컬렉션이 named vectors(dense+sparse) 구조인지."""
        vecs = info.config.params.vectors
        if isinstance(vecs, dict):
            return DENSE_NAME in vecs
        # VectorParams 단독 객체면 unnamed = vector 모드
        return False

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]

        if self._collection not in existing:
            # 신규 생성 — 모드별로 구조 결정
            if self._search_mode == "hybrid":
                self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config={
                        DENSE_NAME: VectorParams(size=self._dim, distance=Distance.COSINE),
                    },
                    sparse_vectors_config={
                        SPARSE_NAME: SparseVectorParams(),
                    },
                )
                logger.info(
                    f"Qdrant 하이브리드 컬렉션 생성: {self._collection} "
                    f"(dense dim={self._dim}, sparse={SPARSE_NAME})"
                )
            else:
                self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
                )
                logger.info(f"Qdrant 컬렉션 생성: {self._collection} (dim={self._dim})")
            return

        # 존재 시 모드 일치 검증
        info = self._client.get_collection(self._collection)
        is_hybrid = self._is_hybrid_collection(info)

        if self._search_mode == "hybrid" and not is_hybrid:
            raise CollectionDimensionMismatch(
                f"Qdrant 컬렉션 '{self._collection}'이 vector 모드(unnamed)인데 "
                f"SEARCH_MODE=hybrid로 실행됨. 재인덱싱 필요: "
                f"python pipeline/rebuild_index.py  (컬렉션 재생성)"
            )
        if self._search_mode == "vector" and is_hybrid:
            raise CollectionDimensionMismatch(
                f"Qdrant 컬렉션 '{self._collection}'이 hybrid 모드(named vectors)인데 "
                f"SEARCH_MODE=vector로 실행됨. 재인덱싱 필요."
            )

        # dense 차원 검증
        if is_hybrid:
            current = info.config.params.vectors[DENSE_NAME].size
        else:
            current = info.config.params.vectors.size
        if current != self._dim:
            raise CollectionDimensionMismatch(
                f"Qdrant 컬렉션 '{self._collection}'의 dense 차원({current})이 "
                f"현재 임베딩 차원({self._dim})과 다릅니다. 재인덱싱 필요."
            )

    def _ensure_payload_indexes(self) -> None:
        """TASK-015: 검색 필터·집계용 payload 인덱스. 이미 있으면 무해(무시).

        - metadata.doc_id: 문서 단위 조회·삭제(이미 사용 중)
        - metadata.doc_type: enum 필터 (book/article/...)
        - metadata.category: 카테고리 단일 문자열 필터
        - metadata.tags: 태그 배열 (Qdrant keyword 인덱스가 array를 자동 지원)
        """
        targets = [
            "metadata.doc_id",
            "metadata.doc_type",
            "metadata.category",
            "metadata.tags",
            # TASK-020 (ADR-029): series_filter 검색 + 도서관 그룹화
            "metadata.series_id",
            # TASK-022 (ADR-035): heading prefix 동반 검색.
            # array 타입 keyword 인덱스 — Qdrant는 array 원소 단위 매칭을 지원하므로
            # heading_path[i] 단일 값 매칭으로 prefix 첫 토큰을 골라낼 수 있다.
            "metadata.heading_path",
        ]
        for field_name in targets:
            try:
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception as e:
                # 이미 존재하면 ApiException 발생 — 무시
                logger.debug(f"payload 인덱스 {field_name} skip: {e}")

    # ─────────────────────────────────────────────────────
    # 문서 추가
    # ─────────────────────────────────────────────────────

    def add_documents(self, documents: list[Document]) -> list[str]:
        if not documents:
            return []

        if self._search_mode == "vector":
            lc_docs = [
                LCDocument(page_content=d.content, metadata=d.metadata) for d in documents
            ]
            ids = self._store.add_documents(lc_docs)
            logger.info(f"{len(ids)}개 벡터 저장 완료")
            return ids

        # hybrid: dense + sparse 동시 upsert (raw SDK)
        # 메모리 캡: EMBED_BATCH_SIZE 단위로 임베딩→PointStruct→upsert→폐기.
        ids: list[str] = []
        total = len(documents)
        for start in range(0, total, EMBED_BATCH_SIZE):
            chunk_docs = documents[start:start + EMBED_BATCH_SIZE]
            texts = [d.content for d in chunk_docs]
            dense_vecs = self._embeddings.embed_documents(texts)
            sparse_vecs = self._sparse.embed_documents(texts)

            points: list[PointStruct] = []
            for doc, dv, sv in zip(chunk_docs, dense_vecs, sparse_vecs):
                pid = str(uuid.uuid4())
                ids.append(pid)
                points.append(
                    PointStruct(
                        id=pid,
                        vector={
                            DENSE_NAME: dv,
                            SPARSE_NAME: SparseVector(
                                indices=sv.indices, values=sv.values
                            ),
                        },
                        payload={
                            "page_content": doc.content,
                            "metadata": doc.metadata,
                        },
                    )
                )

            for u_start in range(0, len(points), UPSERT_BATCH_SIZE):
                batch = points[u_start:u_start + UPSERT_BATCH_SIZE]
                self._client.upsert(collection_name=self._collection, points=batch)

        logger.info(
            f"{len(ids)}개 하이브리드 벡터(dense+sparse) 저장 완료 "
            f"(embed_batch={EMBED_BATCH_SIZE}, upsert_batch={UPSERT_BATCH_SIZE})"
        )
        return ids

    # ─────────────────────────────────────────────────────
    # 검색
    # ─────────────────────────────────────────────────────

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 20,
        score_threshold: float = 0.0,
        doc_id: Optional[str] = None,
        category: Optional[str] = None,
        series_id: Optional[str] = None,
    ) -> list[ScoredChunk]:
        # TASK-019/020: doc_id/category/series_id 동시 지정 시 모두 must로 AND. 우선순위 분기는
        # pipeline 레이어에서 결정하므로 여기서는 받은 인자 그대로 AND 적용.
        must: list = []
        if doc_id:
            must.append(FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id)))
        if category:
            must.append(FieldCondition(key="metadata.category", match=MatchValue(value=category)))
        if series_id:
            must.append(FieldCondition(key="metadata.series_id", match=MatchValue(value=series_id)))
        filter_condition: Optional[Filter] = Filter(must=must) if must else None

        if self._search_mode == "vector":
            results = self._store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter_condition,
            )
            return [
                ScoredChunk(content=doc.page_content, metadata=doc.metadata, score=score)
                for doc, score in results
                if score >= score_threshold
            ]

        # hybrid: Qdrant Query API + RRF 병합
        dense_q = self._embeddings.embed_query(query)
        sparse_q = self._sparse.embed_query(query)

        response = self._client.query_points(
            collection_name=self._collection,
            prefetch=[
                Prefetch(query=dense_q, using=DENSE_NAME, limit=k * 2),
                Prefetch(
                    query=SparseVector(indices=sparse_q.indices, values=sparse_q.values),
                    using=SPARSE_NAME,
                    limit=k * 2,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            query_filter=filter_condition,
            limit=k,
            with_payload=True,
            with_vectors=False,
        )

        chunks: list[ScoredChunk] = []
        for p in response.points:
            # RRF 점수는 일반적으로 0~1 범위 밖. score_threshold는 여기서는 원점수 그대로 비교.
            if p.score < score_threshold:
                continue
            payload = p.payload or {}
            chunks.append(
                ScoredChunk(
                    content=payload.get("page_content", ""),
                    metadata=payload.get("metadata", {}),
                    score=float(p.score),
                )
            )
        return chunks

    # ─────────────────────────────────────────────────────
    # 삭제·스크롤
    # ─────────────────────────────────────────────────────

    def delete_by_doc_id(self, doc_id: str) -> bool:
        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="metadata.doc_id",
                                match=MatchValue(value=doc_id),
                            )
                        ]
                    )
                ),
            )
            logger.info(f"doc_id={doc_id} 벡터 삭제 완료")
            return True
        except Exception as e:
            logger.error(f"벡터 삭제 실패: {e}")
            return False

    def as_retriever(self, k: int = 20):
        # hybrid 모드에서는 langchain_qdrant의 retriever를 쓸 수 없어 미지원
        if self._search_mode != "vector":
            raise NotImplementedError(
                "as_retriever()는 vector 모드에서만 지원. hybrid는 similarity_search_with_score 사용."
            )
        return self._store.as_retriever(search_kwargs={"k": k})

    def set_classification_payload(
        self,
        doc_id: str,
        doc_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """TASK-015: doc_id에 속한 모든 청크의 payload에 분류 정보를 일괄 업데이트.

        Qdrant `set_payload`에 `key="metadata"`를 주면 nested 업데이트 — 즉
        `payload["metadata"][k] = v` 형태로 들어가 Filter `key="metadata.category"`
        (dot-notation = nested 해석)와 매칭됨. 인덱싱 시점에 payload["metadata"]가 dict로
        존재하는 게 전제 (add_documents에서 보장).

        과거 버전(0.23.x 이전)은 key 파라미터 없이 호출해 flat key
        `payload["metadata.category"]` 로 저장했고, 그 결과 Filter가 매칭하지 않아
        category_filter가 항상 0건이었다(0.23.1 fix). 기존 데이터는 별도 마이그레이션 필요.

        None인 인자는 손대지 않는다.
        """
        payload: dict = {}
        if doc_type is not None:
            payload["doc_type"] = doc_type
        if category is not None:
            payload["category"] = category
        if tags is not None:
            payload["tags"] = list(tags)
        if not payload:
            return False
        try:
            self._client.set_payload(
                collection_name=self._collection,
                payload=payload,
                key="metadata",
                points=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.doc_id",
                            match=MatchValue(value=doc_id),
                        )
                    ]
                ),
            )
            return True
        except Exception as e:
            logger.warning(f"set_payload 실패 doc_id={doc_id}: {e}")
            return False

    def set_series_payload(
        self,
        doc_ids: list[str],
        series_id: Optional[str],
        series_title: Optional[str] = None,
    ) -> bool:
        """TASK-020 (ADR-029): doc_ids에 속한 모든 청크의 metadata에 series 정보 부분 갱신.

        nested 업데이트 — `payload["metadata"]["series_id"]`/`series_title` 으로 저장되어
        `Filter(key="metadata.series_id")`와 매칭됨. 분리 시 `series_id=None`을 넘기면
        해당 키를 비운다(빈 문자열로 마킹) — Qdrant set_payload는 None 키를 자동 삭제하지 않으므로
        검색 필터에서 빈 문자열을 fallback로 거른다는 가정.
        """
        if not doc_ids:
            return False
        payload: dict = {
            "series_id": series_id or "",
            "series_title": series_title or "",
        }
        try:
            self._client.set_payload(
                collection_name=self._collection,
                payload=payload,
                key="metadata",
                points=Filter(
                    should=[
                        FieldCondition(key="metadata.doc_id", match=MatchValue(value=did))
                        for did in doc_ids
                    ]
                ),
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"set_series_payload 실패 docs={doc_ids}: {e}")
            return False

    def scroll_by_heading_prefix(
        self,
        doc_id: str,
        prefix_tokens: list[str],
        exclude_chunk_indices: Optional[list[int]] = None,
        limit: int = 10,
    ) -> list[ScoredChunk]:
        """TASK-022 (ADR-035): heading prefix 동반 검색.

        같은 doc_id 안에서 `metadata.heading_path` 가 prefix_tokens 모두를 포함하는
        청크를 limit개 스크롤한다. heading_path는 list[str] payload이고 Qdrant는 array
        원소 단위 매칭을 지원하므로, prefix_tokens 각각을 must FieldCondition로 AND한다.

        prefix_tokens가 비어 있으면 빈 리스트 반환(전체 doc 청크 회수는 의도 아님).
        exclude_chunk_indices에 든 chunk_index는 결과에서 제외(self·중복 회피용).
        """
        if not prefix_tokens:
            return []

        must = [FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))]
        for tok in prefix_tokens:
            must.append(FieldCondition(key="metadata.heading_path", match=MatchValue(value=tok)))

        try:
            result, _ = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=Filter(must=must),
                limit=max(limit + len(exclude_chunk_indices or []), limit),
                with_payload=True,
                with_vectors=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"scroll_by_heading_prefix 실패 doc_id={doc_id} prefix={prefix_tokens}: {e}"
            )
            return []

        excluded = set(exclude_chunk_indices or [])
        chunks: list[ScoredChunk] = []
        for p in result:
            payload = p.payload or {}
            metadata = payload.get("metadata", {})
            ci = metadata.get("chunk_index")
            if ci in excluded:
                continue
            chunks.append(
                ScoredChunk(
                    content=payload.get("page_content", ""),
                    metadata=metadata,
                    score=0.0,
                )
            )
            if len(chunks) >= limit:
                break
        return chunks

    def scroll_by_doc_id(self, doc_id: str, limit: int = 10) -> list[ScoredChunk]:
        """특정 doc_id의 청크를 chunk_index 순으로 스크롤. 관리자 UI용."""
        result, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        chunks: list[ScoredChunk] = []
        for p in result:
            payload = p.payload or {}
            chunks.append(
                ScoredChunk(
                    content=payload.get("page_content", ""),
                    metadata=payload.get("metadata", {}),
                    score=0.0,
                )
            )
        chunks.sort(key=lambda c: str(c.metadata.get("chunk_index", "")))
        return chunks
