from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # OpenAI
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    openai_chat_temperature: float = 0.0

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

    # LangSmith (LangChain이 os.environ을 직접 읽으므로 필드는 관측·검증용)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "knowledge-rag"
    langchain_endpoint: str = "https://api.smith.langchain.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
