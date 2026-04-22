from functools import lru_cache
from sqlalchemy.orm import Session
from typing import Generator

from apps.config import get_settings
from packages.db.connection import get_session
from packages.llm.embeddings import build_embeddings
from packages.llm.chat import build_chat
from packages.rag.pipeline import RAGPipeline
from packages.rag.reranker import get_reranker
from packages.vectorstore.qdrant_store import QdrantDocumentStore


@lru_cache
def get_pipeline() -> RAGPipeline:
    settings = get_settings()
    embeddings = build_embeddings(settings)
    store = QdrantDocumentStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embeddings=embeddings,
    )
    llm = build_chat(settings)
    reranker = get_reranker(
        backend=settings.reranker_backend,
        model_name=settings.reranker_model_name or None,
    )
    return RAGPipeline(store=store, llm=llm, reranker=reranker, settings=settings)


def get_db() -> Generator[Session, None, None]:
    yield from get_session()
