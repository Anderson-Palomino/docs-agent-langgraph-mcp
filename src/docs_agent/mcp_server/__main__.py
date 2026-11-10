"""Entrada del servidor MCP por stdio: `uv run docs-agent-mcp` o `python -m docs_agent.mcp_server`."""

import logging
import sys

from openai import OpenAI
from pydantic import ValidationError

from docs_agent.config import Settings, get_settings
from docs_agent.db import connect
from docs_agent.mcp_server.server import build_server
from docs_agent.tracing import configure_tracing

OPENAI_MAX_RETRIES = 1
# Espera antes del único reintento del SDK de OpenAI: 0.5 s × jitter (`INITIAL_RETRY_DELAY`), salvo que la
# respuesta traiga `Retry-After` (p. ej. un 429), que el SDK respeta y que ningún timeout nuestro acota.
OPENAI_RETRY_BACKOFF_S = 0.5


def openai_limits(settings: Settings) -> tuple[float, int]:
    """(timeout, max_retries) del cliente OpenAI del servidor, derivados de `MCP_CALL_TIMEOUT_S` (D30).

    El cliente MCP corta la llamada (y la sesión compartida) a los `mcp_call_timeout_s`: los intentos del
    servidor deben terminar antes. Con un reintento y un tercio del presupuesto por intento, el peor caso es
    2 × T/3 + 0.5 s, y queda ~T/3 para Postgres (conexión, presupuesto, búsqueda). Con T=15: 5 s por intento.
    """
    return settings.mcp_call_timeout_s / 3, OPENAI_MAX_RETRIES


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
    timeout_s, max_retries = openai_limits(settings)
    client = OpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=timeout_s, max_retries=max_retries)
    server = build_server(
        settings,
        conn_factory=lambda: connect(settings.database_url),
        client_factory=lambda: client,
    )
    server.run("stdio")


if __name__ == "__main__":
    main()
