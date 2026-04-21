from typing import Optional
from langchain_openai import OpenAIEmbeddings
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

VECTOR_SIZE = 1536  # text-embedding-3-small 차원


class QdrantDocumentStore:
    def __init__(self, url: str, collection: str, embeddings: OpenAIEmbeddings):
        self._client = QdrantClient(url=url)
        self._collection = collection
        self._embeddings = embeddings
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
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info(f"Qdrant 컬렉션 생성: {self._collection}")

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
