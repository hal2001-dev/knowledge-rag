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
) -> list[ScoredChunk]:
    """
    Qdrant에서 initial_k개 후보를 가져온 뒤 주어진 reranker로 재정렬해 top_n개를 반환한다.
    반환 ScoredChunk.score는 reranker 점수(0~1)로 덮어써진다.

    스코프 우선순위 (호출자에서 정렬됨, retriever는 받은 값 그대로 통과):
    - doc_id   : 특정 문서 청크에 한정 (TASK-016 도서관 탭)
    - category : 특정 카테고리(payload.metadata.category) 한정 (TASK-019)
    - series_id: 특정 시리즈(payload.metadata.series_id) 한정 (TASK-020)
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
    return reranker.rerank(query=query, candidates=candidates, top_n=top_n)
