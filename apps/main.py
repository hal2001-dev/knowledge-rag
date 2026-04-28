import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.config import get_settings
from apps.middleware.auth import AuthMiddleware
from apps.routers import conversations, documents, ingest, jobs, query, series
from packages.code.logger import get_logger
from packages.db.connection import init_db
from packages.db.models import Base

logger = get_logger(__name__)


def _configure_langsmith(settings) -> None:
    """LangChain은 os.environ을 직접 읽으므로 Pydantic 값을 환경으로 복사."""
    if not settings.langchain_tracing_v2 or not settings.langchain_api_key:
        logger.info("LangSmith 추적 비활성")
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    logger.info(f"LangSmith 추적 활성: project={settings.langchain_project}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    _configure_langsmith(settings)

    # 업로드 디렉터리 생성
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    # PostgreSQL 초기화
    init_db(settings.postgres_url)
    from packages.db.connection import get_engine
    Base.metadata.create_all(bind=get_engine())

    # Reranker 미리 로드 (첫 질의 지연 최소화)
    if settings.reranker_warmup:
        from packages.code.models import ScoredChunk
        from packages.rag.reranker import get_reranker
        logger.info(f"Reranker warm-up 시작: backend={settings.reranker_backend}")
        r = get_reranker(settings.reranker_backend, settings.reranker_model_name or None)
        dummy = [ScoredChunk(content="warmup", metadata={}, score=0.0)]
        r.rerank(query="warmup", candidates=dummy, top_n=1)
        logger.info("Reranker warm-up 완료")

    yield


app = FastAPI(
    title="Knowledge RAG API",
    description="Docling + Qdrant + PostgreSQL 기반 문서 질의응답 시스템",
    version="0.1.0",
    lifespan=lifespan,
)

# TASK-019 (ADR-030): NextJS dev origin CORS + Clerk 인증 미들웨어 (Origin 분기).
# 미들웨어 등록 순서가 곧 적용 순서의 역순 — 마지막에 등록한 게 가장 바깥쪽.
# CORS는 가장 바깥, Auth는 그 안쪽. OPTIONS preflight는 Auth가 통과시킴.
_settings = get_settings()
app.add_middleware(AuthMiddleware, settings=_settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, tags=["ingest"])
app.include_router(query.router, tags=["query"])
app.include_router(documents.router, tags=["documents"])
app.include_router(conversations.router, tags=["conversations"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(series.router, tags=["series"])


@app.get("/health")
def health():
    return {"status": "ok"}
