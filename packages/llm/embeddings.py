"""
임베딩 백엔드 토글 (ADR-016 / TASK-002).

- openai : `text-embedding-3-small` (1536-d, API 과금, 영어 위주 학습)
- bge-m3 : `BAAI/bge-m3` (1024-d, 다국어 100+, 로컬 실행, 비용 0)

주의: 차원이 다르면 Qdrant 컬렉션도 새로 만들어야 한다. embedding_dim 속성을 노출해
컬렉션 준비 시 참조한다.
"""
from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from apps.config import Settings
from packages.code.logger import get_logger

logger = get_logger(__name__)


_OPENAI_DIM = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class _EmbeddingWithDim(Embeddings):
    """차원 정보를 함께 노출하는 래퍼 — QdrantDocumentStore가 참조."""

    def __init__(self, inner: Embeddings, dim: int, backend: str, model: str):
        self._inner = inner
        self.embedding_dim = dim
        self.backend = backend
        self.model = model

    def embed_documents(self, texts):
        return self._inner.embed_documents(texts)

    def embed_query(self, text):
        return self._inner.embed_query(text)


def build_embeddings(settings: Settings) -> _EmbeddingWithDim:
    backend = (settings.embedding_backend or "openai").lower()
    if backend == "openai":
        model = settings.embedding_model_name or settings.openai_embedding_model
        inner = OpenAIEmbeddings(model=model, openai_api_key=settings.openai_api_key)
        dim = _OPENAI_DIM.get(model, 1536)
        logger.info(f"Embedding backend: openai · model={model} · dim={dim}")
        return _EmbeddingWithDim(inner, dim=dim, backend="openai", model=model)

    if backend == "bge-m3":
        from langchain_huggingface import HuggingFaceEmbeddings
        model = settings.embedding_model_name or "BAAI/bge-m3"
        logger.info(f"Embedding backend: bge-m3 · model={model} (첫 로드 시 ~2.3GB 다운로드)")
        inner = HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        return _EmbeddingWithDim(inner, dim=1024, backend="bge-m3", model=model)

    raise ValueError(f"알 수 없는 EMBEDDING_BACKEND: {backend!r} (허용: openai|bge-m3)")
