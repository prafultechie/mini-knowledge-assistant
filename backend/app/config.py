from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./knowledge.db"
    cors_origins: str = "http://localhost:5173"
    max_document_chars: int = 50000
    max_question_chars: int = 1000
    chunk_size: int = 700
    chunk_overlap: int = 100
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
