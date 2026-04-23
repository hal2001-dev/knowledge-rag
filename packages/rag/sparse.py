"""
Sparse embedding (BM25) 생성기 — TASK-011 하이브리드 검색용.

한국어는 Kiwi 형태소 분석으로 명사·동사·외국어·숫자만 추출 후 BM25에 투입.
영어는 BM25가 내장 토크나이저 사용.
"""
from __future__ import annotations

from dataclasses import dataclass

from packages.code.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SparseVec:
    """Qdrant `SparseVector`로 변환 가능한 표현."""
    indices: list[int]
    values: list[float]


_KOREAN_TAG_PREFIXES = ("N", "V", "SL", "SN", "SH", "XR")  # 명사·동사·외국어·숫자·한자·어근
_kiwi_singleton = None
_bm25_singleton = None


def _get_kiwi():
    global _kiwi_singleton
    if _kiwi_singleton is None:
        from kiwipiepy import Kiwi
        logger.info("Kiwi 형태소 분석기 로드")
        _kiwi_singleton = Kiwi()
    return _kiwi_singleton


def _get_bm25(model_name: str):
    global _bm25_singleton
    if _bm25_singleton is None:
        from fastembed import SparseTextEmbedding
        logger.info(f"SparseTextEmbedding 모델 로드: {model_name}")
        _bm25_singleton = SparseTextEmbedding(model_name=model_name)
    return _bm25_singleton


def _has_korean(text: str) -> bool:
    return any("\uac00" <= ch <= "\ud7a3" for ch in text)


def preprocess(text: str) -> str:
    """한국어면 Kiwi로 명사·동사·외국어·숫자만 추려 공백 조인, 아니면 원문 그대로."""
    if not _has_korean(text):
        return text
    kiwi = _get_kiwi()
    tokens = []
    for t in kiwi.tokenize(text):
        if t.tag.startswith(_KOREAN_TAG_PREFIXES):
            tokens.append(t.form)
    return " ".join(tokens) if tokens else text


class SparseEmbedder:
    """BM25 기반 sparse embedder. 프로세스 전역 싱글톤."""

    def __init__(self, model_name: str = "Qdrant/bm25"):
        self._model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[SparseVec]:
        processed = [preprocess(t) for t in texts]
        bm25 = _get_bm25(self._model_name)
        return [
            SparseVec(indices=list(e.indices), values=list(e.values))
            for e in bm25.embed(processed)
        ]

    def embed_query(self, text: str) -> SparseVec:
        return self.embed_documents([text])[0]
