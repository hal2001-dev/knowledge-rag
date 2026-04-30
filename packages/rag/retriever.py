from packages.vectorstore.qdrant_store import QdrantDocumentStore
from packages.code.models import ScoredChunk
from packages.code.logger import get_logger
from packages.rag.reranker import Reranker

logger = get_logger(__name__)


def retrieve(
    store: QdrantDocumentStore,
    query: str,
    reranker: Reranker,
    initial_k: int = 20,
    top_n: int = 5,
    score_threshold: float = 0.0,
    doc_id: str | None = None,
    category: str | None = None,
    series_id: str | None = None,
    expand_enabled: bool = False,
    expand_prefix_depth: int = 1,
    expand_neighbors: int = 2,
) -> list[ScoredChunk]:
    """
    Qdrant에서 initial_k개 후보를 가져온 뒤 주어진 reranker로 재정렬해 top_n개를 반환한다.
    반환 ScoredChunk.score는 reranker 점수(0~1)로 덮어써진다.

    스코프 우선순위 (호출자에서 정렬됨, retriever는 받은 값 그대로 통과):
    - doc_id   : 특정 문서 청크에 한정 (TASK-016 도서관 탭)
    - category : 특정 카테고리(payload.metadata.category) 한정 (TASK-019)
    - series_id: 특정 시리즈(payload.metadata.series_id) 한정 (TASK-020)

    TASK-022 (ADR-035): expand_enabled=True면 reranker 통과한 hit 청크 각각에 대해
    `metadata.heading_path[:expand_prefix_depth]` prefix를 공유하는 같은 doc_id 인접
    청크를 expand_neighbors개 회수해 companion으로 결과 list 끝에 append한다.
    companion은 score=0.0, metadata.companion=True 마킹. (doc_id, chunk_index)
    중복은 제거. 호출자(pipeline)가 sources 빌드 시 companion을 제외하고 LLM
    컨텍스트에만 들어가도록 처리한다.
    """
    candidates = store.similarity_search_with_score(
        query=query,
        k=initial_k,
        score_threshold=score_threshold,
        doc_id=doc_id,
        category=category,
        series_id=series_id,
    )
    if not candidates:
        return []
    hits = reranker.rerank(query=query, candidates=candidates, top_n=top_n)
    if not expand_enabled or not hits:
        return hits

    # depth 0이면 expand 의미 없음(전체 doc 회수와 동일) — no-op로 취급
    if expand_prefix_depth <= 0 or expand_neighbors <= 0:
        return hits

    # 중복 제거 키 — (doc_id, chunk_index)
    seen: set[tuple[str, object]] = set()
    for h in hits:
        seen.add((h.metadata.get("doc_id"), h.metadata.get("chunk_index")))

    companions: list[ScoredChunk] = []
    for hit in hits:
        h_doc_id = hit.metadata.get("doc_id")
        if not h_doc_id:
            continue
        heading_path = hit.metadata.get("heading_path") or []
        if not isinstance(heading_path, list) or not heading_path:
            continue
        prefix_tokens = [t for t in heading_path[:expand_prefix_depth] if isinstance(t, str) and t.strip()]
        if not prefix_tokens:
            continue

        # 같은 hit 자기 자신 + 이미 seen에 있는 청크는 exclude로 1차 필터
        exclude_indices = [
            ci for (did, ci) in seen
            if did == h_doc_id and isinstance(ci, int)
        ]
        neighbors = store.scroll_by_heading_prefix(
            doc_id=h_doc_id,
            prefix_tokens=prefix_tokens,
            exclude_chunk_indices=exclude_indices,
            limit=expand_neighbors,
        )
        for n in neighbors:
            key = (n.metadata.get("doc_id"), n.metadata.get("chunk_index"))
            if key in seen:
                continue
            seen.add(key)
            n.metadata = {**n.metadata, "companion": True}
            companions.append(n)

    if companions:
        logger.info(
            f"heading expand — hits={len(hits)} companions={len(companions)} "
            f"(depth={expand_prefix_depth}, neighbors={expand_neighbors})"
        )
    return hits + companions
