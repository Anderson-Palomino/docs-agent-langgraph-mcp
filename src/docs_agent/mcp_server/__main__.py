"""Entrada del servidor MCP por stdio: `uv run docs-agent-mcp` o `python -m docs_agent.mcp_server`."""

import logging
import sys

from openai import OpenAI
from pydantic import ValidationError

from docs_agent.config import get_settings
from docs_agent.db import connect
from docs_agent.mcp_server.server import build_server
from docs_agent.tracing import configure_tracing

OPENAI_TIMEOUT_S = 30
OPENAI_MAX_RETRIES = 2


def _scope_error(exc: ValidationError) -> str | None:
    for err in exc.errors():
        if err.get("loc") and err["loc"][0] == "mcp_budget_scope":
            return f"invalid MCP_BUDGET_SCOPE: {err.get('input')} (expected mcp|ask)"
    return None


def main() -> None:
    # stdout es el canal MCP: todo lo demás va a stderr, en UTF-8 (las líneas de log usan → y ·).
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    # Configurar logging antes de crear MCPServer: su basicConfig queda sin efecto y sus logs van a stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = get_settings()
    except ValidationError as exc:
        # Nunca imprimir el objeto ni la excepción completa: podría incluir valores de .env.
        print(_scope_error(exc) or "invalid settings: " + ", ".join(
            ".".join(str(p) for p in e.get("loc", ())) for e in exc.errors()
        ), file=sys.stderr)
        sys.exit(1)
    configure_tracing(settings)
    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=OPENAI_TIMEOUT_S,
        max_retries=OPENAI_MAX_RETRIES,
    )
    server = build_server(
        settings,
        conn_factory=lambda: connect(settings.database_url),
        client_factory=lambda: client,
    )
    server.run("stdio")


if __name__ == "__main__":
    main()
