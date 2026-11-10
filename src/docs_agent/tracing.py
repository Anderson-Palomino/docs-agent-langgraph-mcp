"""LangSmith opcional: `pydantic-settings` lee `.env`, pero LangSmith solo mira `os.environ`."""

import os

from docs_agent.config import Settings


def configure_tracing(settings: Settings) -> bool:
    """Copia la configuración de LangSmith a `os.environ` si el tracing está activo y hay key."""
    api_key = settings.langsmith_api_key.get_secret_value()
    if not (settings.langsmith_tracing and api_key):
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    return True
