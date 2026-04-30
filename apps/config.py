from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # OpenAI (embedding 전용 + LLM legacy fallback)
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"

    # Embedding 백엔드 토글 (ADR-016, TASK-002)
    # "openai" | "bge-m3" (다국어 로컬, 1024-d, 비용 0)
    embedding_backend: str = "openai"
    embedding_model_name: str = ""  # 빈 값이면 backend별 기본
    embedding_warmup: bool = False  # True면 startup에서 모델 preload (BGE-M3만 의미)
    openai_chat_model: str = "gpt-4o-mini"          # legacy — LLM_MODEL 비었을 때 fallback
    openai_chat_temperature: float = 0.0             # legacy — LLM_TEMPERATURE 비었을 때 fallback

    # LLM 백엔드 토글 (ADR-014) — OpenAI / GLM / 기타 OpenAI-호환 공급자
    llm_backend: str = "openai"        # "openai" | "glm" | "custom"
    llm_base_url: str = ""             # 빈 값이면 backend별 기본
    llm_api_key: str = ""              # 빈 값이면 OPENAI_API_KEY로 fallback (openai backend 한정)
    llm_model: str = ""                # 빈 값이면 backend별 기본
    llm_temperature: str = ""  # 빈 문자열이면 openai_chat_temperature fallback. _resolve에서 파싱

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"

    # PostgreSQL
    postgres_url: str = "postgresql://raguser:ragpass@localhost:5432/ragdb"

    # 앱
    upload_dir: str = "./data/uploads"
    markdown_dir: str = "./data/markdown"
    default_top_k: int = 5          # 답변 빈약 보완 (2026-04-29) — 3→5: LLM 컨텍스트 풍부, 같은 섹션 인접 청크 동반 효과
    default_initial_k: int = 20
    default_score_threshold: float = 0.3
    max_upload_size_mb: int = 200
    log_level: str = "INFO"

    # 후속 질문 제안 (TASK-007, ADR-019)
    suggestions_enabled: bool = True
    suggestions_count: int = 3

    # 인덱스 커버리지 카드 (TASK-008, ADR-020 예정)
    index_overview_enabled: bool = True

    # 문서 요약 (TASK-014, ADR-024) — gpt-4o-mini 재활용. 인덱싱 후 비동기 1회 호출.
    summary_enabled: bool = True

    # 색인 워커 분리 (TASK-018, ADR-028) — "queue" | "sync"
    # queue: POST /ingest는 큐 enqueue + 202만, indexer 워커가 처리
    # sync : 기존 동작 (라우트 안에서 인덱싱 직접 수행) — 회귀용
    ingest_mode: str = "queue"

    # 검색 모드 (TASK-011, ADR-023) — vector | hybrid
    search_mode: str = "vector"
    sparse_model_name: str = "Qdrant/bm25"

    # heading prefix 동반 검색 (TASK-022, ADR-035)
    # enabled=false 기본 — 안정화 후 별도 PR로 true 전환. retriever가 hit 청크의
    # heading_path[:prefix_depth]를 공유하는 같은 doc_id 인접 청크를 neighbors개 회수해
    # companion으로 LLM 컨텍스트에 동반(sources에는 노출 안 됨).
    heading_expand_enabled: bool = False
    heading_expand_prefix_depth: int = 1
    heading_expand_neighbors: int = 2

    # Reranker — flashrank(영어) | bge-m3(다국어)
    reranker_backend: str = "flashrank"
    reranker_model_name: str = ""  # 빈 값이면 각 백엔드 기본 모델 사용
    reranker_warmup: bool = False  # True면 startup에서 모델 preload

    # LangSmith (LangChain이 os.environ을 직접 읽으므로 필드는 관측·검증용)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "knowledge-rag"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # TASK-019 (ADR-030) — 인증 미들웨어 토글 + Clerk
    # auth_enabled=false (Phase 1 기본): JWT 미검증. LAN/localhost는 'admin', 외부 origin도 'admin' 통과
    # auth_enabled=true  (Phase 2): JWT 헤더 있으면 Clerk 검증. 헤더 없으면 LAN→'admin', 외부→401
    auth_enabled: bool = False
    clerk_jwks_url: str = ""              # 예: https://<your-app>.clerk.accounts.dev/.well-known/jwks.json
    clerk_issuer: str = ""                # 예: https://<your-app>.clerk.accounts.dev
    # NextJS dev 서버 origin — CORS 허용
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
