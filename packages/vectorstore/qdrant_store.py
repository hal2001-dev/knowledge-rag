from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document as LCDocument
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    Filter,
    FieldCondition,
    FilterSelector,
    MatchValue,
    VectorParams,
)

from packages.code.models import Document, ScoredChunk
from packages.code.logger import get_logger

logger = get_logger(__name__)


class CollectionDimensionMismatch(RuntimeError):
    """기존 컬렉션 차원이 현재 임베딩과 불일치."""


class QdrantDocumentStore:
    def __init__(self, url: str, collection: str, embeddings: Embeddings):
        self._client = QdrantClient(url=url)
        self._collection = collection
        self._embeddings = embeddings
        # embedding_dim이 없으면 기본 1536 (text-embedding-3-small)
        self._dim = int(getattr(embeddings, "embedding_dim", 1536))
        self._ensure_collection()
        self._store = QdrantVectorStore(
            client=self._client,
            collection_name=collection,
            embedding=embeddings,
        )

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )
            logger.info(f"Qdrant 컬렉션 생성: {self._collection} (dim={self._dim})")
            return
        # 존재하면 차원 검증
        info = self._client.get_collection(self._collection)
        current = info.config.params.vectors.size if hasattr(info.config.params.vectors, "size") else None
        if current is not None and current != self._dim:
            raise CollectionDimensionMismatch(
                f"Qdrant 컬렉션 '{self._collection}'의 차원({current})이 "
                f"현재 임베딩 차원({self._dim})과 다릅니다. "
                f"재인덱싱 필요 (pipeline/rebuild_index.py) — 실행 시 컬렉션을 재생성해야 합니다."
            )

    def add_documents(self, documents: list[Document]) -> list[str]:
        if not documents:
            return []
        lc_docs = [
            LCDocument(page_content=d.content, metadata=d.metadata) for d in documents
        ]
        ids = self._store.add_documents(lc_docs)
        logger.info(f"{len(ids)}개 벡터 저장 완료")
        return ids

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 20,
        score_threshold: float = 0.0,
        doc_id: Optional[str] = None,
    ) -> list[ScoredChunk]:
        filter_condition: Optional[Filter] = None
        if doc_id:
            filter_condition = Filter(
                must=[FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))]
            )

        results = self._store.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter_condition,
        )

        chunks = [
            ScoredChunk(content=doc.page_content, metadata=doc.metadata, score=score)
            for doc, score in results
            if score >= score_threshold
        ]
        return chunks

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
        return self._store.as_retriever(search_kwargs={"k": k})

    def scroll_by_doc_id(self, doc_id: str, limit: int = 10) -> list[ScoredChunk]:
        """특정 doc_id의 청크를 페이로드 순서(chunk_index 기준)로 스크롤. 관리자 UI용."""
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
            content = payload.get("page_content", "")
            metadata = payload.get("metadata", {})
            chunks.append(ScoredChunk(content=content, metadata=metadata, score=0.0))
        # chunk_index로 정렬 (int/str 혼재 가능성 방어)
        chunks.sort(key=lambda c: str(c.metadata.get("chunk_index", "")))
        return chunks
