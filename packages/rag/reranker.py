"""
재순위(Reranker) 추상화 + 2종 백엔드 구현.

선택 기준 요약:
  - flashrank : 영어 MARCO 학습, 로드 빠름(수 초), 한↔영 크로스 약함
  - bge-m3    : 다국어(한/영/일 포함 100+ 언어), 로드 30~60초, ~570MB, 추론 100~300ms/청크
"""
from __future__ import annotations

from typing import Protocol

from packages.code.models import ScoredChunk
from packages.code.logger import get_logger

logger = get_logger(__name__)


class Reranker(Protocol):
    """재순위 백엔드가 구현해야 하는 최소 인터페이스."""

    backend: str

    def rerank(
        self,
        query: str,
        candidates: list[ScoredChunk],
        top_n: int,
    ) -> list[ScoredChunk]:
        ...


# ─── FlashRank (영어 MARCO) ──────────────────────────────────────────

_flashrank_singleton = None


class FlashRankReranker:
    backend = "flashrank"

    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2"):
        self._model_name = model_name

    def _ranker(self):
        global _flashrank_singleton
        if _flashrank_singleton is None:
            from flashrank import Ranker
            logger.info(f"FlashRank 모델 로드: {self._model_name}")
            _flashrank_singleton = Ranker(model_name=self._model_name)
        return _flashrank_singleton

    def rerank(
        self,
        query: str,
        candidates: list[ScoredChunk],
        top_n: int,
    ) -> list[ScoredChunk]:
        if not candidates:
            return []
        from flashrank import RerankRequest
        passages = [{"id": i, "text": c.content} for i, c in enumerate(candidates)]
        ranked = self._ranker().rerank(RerankRequest(query=query, passages=passages))
        out: list[ScoredChunk] = []
        for r in ranked[:top_n]:
            orig = candidates[r["id"]]
            out.append(ScoredChunk(content=orig.content, metadata=orig.metadata, score=float(r["score"])))
        return out


# ─── BGE-reranker-v2-m3 (다국어) ─────────────────────────────────────

_bge_singleton = None


class BgeM3Reranker:
    backend = "bge-m3"

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self._model_name = model_name

    def _model(self):
        global _bge_singleton
        if _bge_singleton is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"BGE reranker 모델 로드: {self._model_name} (첫 로드 시 ~570MB 다운로드)")
            # max_length=512는 cross-encoder 기본 — 긴 청크는 내부에서 자름
            _bge_singleton = CrossEncoder(self._model_name, max_length=512)
        return _bge_singleton

    def rerank(
        self,
        query: str,
        candidates: list[ScoredChunk],
        top_n: int,
    ) -> list[ScoredChunk]:
        if not candidates:
            return []
        pairs = [(query, c.content) for c in candidates]
        # logits → sigmoid(0~1) 스케일로 변환해 FlashRank와 의미적으로 비교 가능하게 한다
        scores = self._model().predict(pairs, activation_fn=None, convert_to_numpy=True)
        import math
        sigmoid_scores = [1.0 / (1.0 + math.exp(-float(s))) for s in scores]

        scored = sorted(
            zip(candidates, sigmoid_scores), key=lambda p: p[1], reverse=True
        )[:top_n]
        return [
            ScoredChunk(content=c.content, metadata=c.metadata, score=float(s))
            for c, s in scored
        ]


# ─── 팩토리 ──────────────────────────────────────────────────────────

_reranker_singleton: Reranker | None = None


def get_reranker(backend: str, model_name: str | None = None) -> Reranker:
    """프로세스 전역 싱글톤. backend 변경 시 교체."""
    global _reranker_singleton
    if _reranker_singleton is not None and _reranker_singleton.backend == backend:
        return _reranker_singleton

    backend = (backend or "flashrank").lower()
    if backend == "bge-m3":
        _reranker_singleton = BgeM3Reranker(model_name or "BAAI/bge-reranker-v2-m3")
    elif backend == "flashrank":
        _reranker_singleton = FlashRankReranker(model_name or "ms-marco-MiniLM-L-12-v2")
    else:
        raise ValueError(f"알 수 없는 RERANKER_BACKEND: {backend!r} (허용: flashrank|bge-m3)")

    logger.info(f"Reranker backend 선택: {_reranker_singleton.backend}")
    return _reranker_singleton
