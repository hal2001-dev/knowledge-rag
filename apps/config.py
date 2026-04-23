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
    default_top_k: int = 3
    default_initial_k: int = 20
    default_score_threshold: float = 0.3
    max_upload_size_mb: int = 200
    log_level: str = "INFO"

    # 후속 질문 제안 (TASK-007, ADR-019)
    suggestions_enabled: bool = True
    suggestions_count: int = 3

    # 인덱스 커버리지 카드 (TASK-008, ADR-020 예정)
    index_overview_enabled: bool = True

    # Reranker — flashrank(영어) | bge-m3(다국어)
    reranker_backend: str = "flashrank"
    reranker_model_name: str = ""  # 빈 값이면 각 백엔드 기본 모델 사용
    reranker_warmup: bool = False  # True면 startup에서 모델 preload

    # LangSmith (LangChain이 os.environ을 직접 읽으므로 필드는 관측·검증용)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "knowledge-rag"
    langchain_endpoint: str = "https://api.smith.langchain.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
