import time
import uuid
from pathlib import Path

from langchain_openai import ChatOpenAI
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree, tracing_context

from apps.config import Settings
from packages.code.models import DocRecord
from packages.code.logger import get_logger
from packages.loaders.factory import get_loader
from packages.rag.chunker import chunk_documents
from packages.rag.generator import generate
from packages.rag.reranker import Reranker
from packages.rag.retriever import retrieve
from packages.vectorstore.qdrant_store import QdrantDocumentStore

logger = get_logger(__name__)


class RAGPipeline:
    def __init__(
        self,
        store: QdrantDocumentStore,
        llm: ChatOpenAI,
        reranker: Reranker,
        settings: Settings,
    ):
        self._store = store
        self._llm = llm
        self._reranker = reranker
        self._settings = settings

    @traceable(run_type="chain", name="rag.ingest")
    def ingest(
        self,
        file_path: str,
        title: str,
        source: str = "",
        doc_id: str | None = None,
        content_hash: str | None = None,
    ) -> DocRecord:
        doc_id = doc_id or str(uuid.uuid4())
        file_type = Path(file_path).suffix.lstrip(".").lower()
        start = time.monotonic()

        logger.info(f"수집 시작: doc_id={doc_id}, file={file_path}")

        t0 = time.monotonic()
        loader = get_loader(file_path, markdown_save_dir=self._settings.markdown_dir)
        documents = loader.load(file_path=file_path, doc_id=doc_id, title=title)
        parse_ms = int((time.monotonic() - t0) * 1000)

        t0 = time.monotonic()
        chunks = chunk_documents(documents)
        chunk_ms = int((time.monotonic() - t0) * 1000)

        has_tables = any(d.metadata.get("content_type") == "table" for d in chunks)
        has_images = any(d.metadata.get("content_type") == "image" for d in chunks)

        t0 = time.monotonic()
        self._store.add_documents(chunks)
        store_ms = int((time.monotonic() - t0) * 1000)

        total_ms = int((time.monotonic() - start) * 1000)
        record = DocRecord(
            doc_id=doc_id,
            title=title,
            source=source or file_path,
            file_type=file_type,
            chunk_count=len(chunks),
            has_tables=has_tables,
            has_images=has_images,
            indexed_at="",
            status="done",
            content_hash=content_hash,
        )
        logger.info(
            f"수집 완료: {len(chunks)}개 청크 "
            f"(파싱 {parse_ms}ms, 청킹 {chunk_ms}ms, 저장 {store_ms}ms, 총 {total_ms}ms, "
            f"테이블: {has_tables}, 이미지: {has_images})"
        )
        return record

    @traceable(run_type="chain", name="rag.query")
    def query(
        self,
        question: str,
        top_k: int | None = None,
        initial_k: int | None = None,
        score_threshold: float | None = None,
        history: list[dict] | None = None,
        doc_filter: str | None = None,
        category_filter: str | None = None,
        series_filter: str | None = None,
    ) -> dict:
        top_k = top_k or self._settings.default_top_k
        initial_k = initial_k or self._settings.default_initial_k
        score_threshold = score_threshold if score_threshold is not None else self._settings.default_score_threshold

        # 활성 스코프 우선순위 doc > category > series (한 번에 하나, ADR-029).
        # 상위 우선순위가 들어오면 하위 인자는 무시.
        effective_category = None if doc_filter else category_filter
        effective_series = None if (doc_filter or effective_category) else series_filter

        llm_model = getattr(self._llm, "model_name", None) or getattr(self._llm, "model", "")
        llm_backend = self._settings.llm_backend or "openai"
        logger.info(
            f"질의: '{question}' (history={len(history or [])}턴, "
            f"reranker={self._reranker.backend}, llm={llm_backend}:{llm_model})"
        )
        start = time.monotonic()

        scope_tags = []
        if doc_filter:
            scope_tags.append(f"doc_filter:{doc_filter[:8]}")
        elif effective_category:
            scope_tags.append(f"category_filter:{effective_category}")
        elif effective_series:
            scope_tags.append(f"series_filter:{effective_series[:12]}")

        scope_tag_list = [
            f"reranker:{self._reranker.backend}",
            f"llm:{llm_backend}",
            f"suggestions:{self._settings.suggestions_enabled}",
        ] + scope_tags
        scope_metadata = {
            "reranker_backend": self._reranker.backend,
            "llm_backend": llm_backend,
            "suggestions_enabled": self._settings.suggestions_enabled,
            "suggestions_count": self._settings.suggestions_count,
            "llm_model": llm_model,
            "doc_filter": doc_filter,
            "category_filter": effective_category,
            "series_filter": effective_series,
        }

        # @traceable이 만든 부모 run(rag.query)에 직접 메타/태그 부여 — tracing_context는 자식 run에만 적용됨
        parent_run = get_current_run_tree()
        if parent_run is not None:
            parent_run.add_metadata(scope_metadata)
            parent_run.add_tags(scope_tag_list)

        with tracing_context(tags=scope_tag_list, metadata=scope_metadata):
            chunks = retrieve(
                store=self._store,
                query=question,
                reranker=self._reranker,
                initial_k=initial_k,
                top_n=top_k,
                score_threshold=score_threshold,
                doc_id=doc_filter,
                category=effective_category,
                series_id=effective_series,
            )

        if not chunks:
            return {
                "answer": "관련 문서를 찾지 못했습니다.",
                "sources": [],
                "latency_ms": int((time.monotonic() - start) * 1000),
                "suggestions": [],
            }

        gen_result = generate(
            llm=self._llm,
            question=question,
            chunks=chunks,
            history=history,
            suggestions_enabled=self._settings.suggestions_enabled,
            suggestions_count=self._settings.suggestions_count,
        )
        answer = gen_result["answer"]
        suggestions = gen_result.get("suggestions", [])
        latency_ms = int((time.monotonic() - start) * 1000)

        sources = [
            {
                "doc_id": c.metadata.get("doc_id"),
                "title": c.metadata.get("title"),
                "page": c.metadata.get("page"),
                "content_type": c.metadata.get("content_type", "text"),
                "score": round(c.score, 4),
                "excerpt": c.content[:200],
            }
            for c in chunks
        ]

        logger.info(
            f"질의 완료: {latency_ms}ms, {len(sources)}개 소스, suggestions={len(suggestions)}"
        )
        return {
            "answer": answer,
            "sources": sources,
            "latency_ms": latency_ms,
            "suggestions": suggestions,
        }
