from functools import lru_cache
from sqlalchemy.orm import Session
from typing import Generator

from apps.config import get_settings
from packages.db.connection import get_session
from packages.llm.embeddings import build_embeddings
from packages.llm.chat import build_chat
from packages.vectorstore.qdrant_store import QdrantDocumentStore
from packages.rag.pipeline import RAGPipeline


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
    return RAGPipeline(store=store, llm=llm, settings=settings)


def get_db() -> Generator[Session, None, None]:
    yield from get_session()
