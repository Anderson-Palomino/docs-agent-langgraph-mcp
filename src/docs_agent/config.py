from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: SecretStr = SecretStr("")
    database_url: str = "postgresql://docs:docs@127.0.0.1:5434/docs"
    test_database_url: str = "postgresql://docs:docs@127.0.0.1:5434/docs_test"
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    fastapi_docs_ref: str = "0.162.0"
    top_k: int = 5
    chunk_max_tokens: int = 800
    chunk_overlap_tokens: int = 100
    ask_daily_token_budget: int = 200_000
    ingest_max_tokens: int = 2_000_000
    no_answer_distance_threshold: float = 0.52  # D21
    mcp_budget_scope: Literal["mcp", "ask"] = "mcp"  # D29
    mcp_daily_token_budget: int = 100_000
    mcp_call_timeout_s: float = 15.0  # D30
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "docs-agent"


@lru_cache
def get_settings() -> Settings:
    return Settings()
