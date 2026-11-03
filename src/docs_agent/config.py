from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    database_url: str = "postgresql://docs:docs@localhost:5434/docs"
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    fastapi_docs_ref: str = "0.162.0"
    top_k: int = 5
    chunk_max_tokens: int = 800
    chunk_overlap_tokens: int = 100
    ask_daily_token_budget: int = 200_000
    ingest_max_tokens: int = 2_000_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
