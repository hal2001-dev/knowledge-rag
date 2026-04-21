from flashrank import Ranker, RerankRequest

from packages.vectorstore.qdrant_store import QdrantDocumentStore
from packages.code.models import ScoredChunk
from packages.code.logger import get_logger

logger = get_logger(__name__)

RERANKER_MODEL = "ms-marco-MiniLM-L-12-v2"

# 프로세스 전역 단일 Ranker (모델 로드 비용 ~수 초)
_ranker: Ranker | None = None


def _get_ranker() -> Ranker:
    global _ranker
    if _ranker is None:
        logger.info(f"FlashRank 모델 로드: {RERANKER_MODEL}")
        _ranker = Ranker(model_name=RERANKER_MODEL)
    return _ranker


def retrieve(
    store: QdrantDocumentStore,
    query: str,
    initial_k: int = 20,
    top_n: int = 5,
    score_threshold: float = 0.0,
) -> list[ScoredChunk]:
    """
    Qdrant에서 initial_k개 후보를 가져온 뒤 FlashRank로 재정렬해 top_n개를 반환한다.
    score는 FlashRank 점수(0~1, 높을수록 관련)로 덮어쓴다.
    """
    candidates = store.similarity_search_with_score(
        query=query,
        k=initial_k,
        score_threshold=score_threshold,
    )
    if not candidates:
        return []

    passages = [
        {"id": i, "text": c.content, "meta": {"orig_score": c.score}}
        for i, c in enumerate(candidates)
    ]
    ranked = _get_ranker().rerank(RerankRequest(query=query, passages=passages))

    results: list[ScoredChunk] = []
    for r in ranked[:top_n]:
        orig = candidates[r["id"]]
        results.append(
            ScoredChunk(
                content=orig.content,
                metadata=orig.metadata,
                score=float(r["score"]),
            )
        )
    return results
