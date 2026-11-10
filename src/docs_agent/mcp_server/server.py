"""Servidor MCP (SDK v2, `MCPServer`) con las tres herramientas de `tools.py`.

stdout es el canal MCP en stdio: todo log va a stderr, una línea por llamada.
"""

import sys
import time
from collections.abc import Callable
from typing import Any

import openai
import psycopg
from langsmith import traceable
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from docs_agent.budget import BudgetExceeded
from docs_agent.config import Settings
from docs_agent.mcp_server import tools

SERVER_NAME = "docs-agent"
QUERY_LOG_CHARS = 60

INSTRUCTIONS = (
    "Tools over the indexed FastAPI documentation (version {ref}). Answer ONLY with what these tools return "
    "and cite the exact URL. Use search_docs first, then get_section to read a full section. If search_docs "
    "returns in_corpus=false, say the indexed documentation does not cover it. Mentioning is not documenting: "
    "if results only mention a technology (for example another framework) without explaining how to use it, "
    "say the documentation does not cover it — at most, that it is mentioned — and never fill in from general "
    "knowledge."
)

LIST_SOURCES_DESC = (
    "Describe the indexed corpus: project, documentation version and how many pages, chunks and sections it has."
)
SEARCH_DOCS_DESC = (
    "Semantic search over the indexed FastAPI documentation. Returns the top-k chunks (title, url, cosine "
    "distance, 300-char snippet), best_distance and in_corpus. If in_corpus is false, the docs do not cover "
    "the question: do not answer from general knowledge. k is clamped to 1..10."
)
GET_SECTION_DESC = (
    "Full Markdown of one documentation section by its exact URL (as returned by search_docs). A page URL "
    "without #anchor returns the page intro plus the list of its sections."
)


def _log(line: str) -> None:
    print(f"[mcp] {line}", file=sys.stderr, flush=True)


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _short_query(query: str) -> str:
    q = " ".join(query.split())
    return q if len(q) <= QUERY_LOG_CHARS else q[:QUERY_LOG_CHARS] + "…"


def _run(prefix: str, fn: Callable[[], dict], summary: Callable[[dict], str]) -> dict:
    """Ejecuta la herramienta, escribe la línea de log y convierte fallos esperados en error MCP."""
    start = time.perf_counter()
    try:
        out = fn()
    except LookupError as exc:
        _log(f"{prefix} → ERROR Unknown section URL · {_ms(start)} ms")
        raise ToolError(str(exc)) from exc
    except BudgetExceeded as exc:
        _log(f"{prefix} → ERROR daily token budget exceeded · {_ms(start)} ms")
        raise ToolError(str(exc)) from exc
    except openai.OpenAIError as exc:
        _log(f"{prefix} → ERROR upstream model error ({type(exc).__name__}) · {_ms(start)} ms")
        raise ToolError("Upstream model error") from exc
    except psycopg.Error as exc:
        _log(f"{prefix} → ERROR database unavailable ({type(exc).__name__}) · {_ms(start)} ms")
        raise ToolError("Database unavailable") from exc
    _log(f"{prefix} → {summary(out)} · {_ms(start)} ms")
    return out


def build_server(
    settings: Settings,
    conn_factory: Callable[[], psycopg.Connection],
    client_factory: Callable[[], Any],
) -> MCPServer:
    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS.format(ref=settings.fastapi_docs_ref))

    def with_conn(fn: Callable[[psycopg.Connection], dict]) -> dict:
        conn = conn_factory()
        try:
            return fn(conn)
        finally:
            conn.close()

    @server.tool(description=LIST_SOURCES_DESC)
    @traceable(name="list_sources", run_type="tool")
    def list_sources() -> dict[str, Any]:
        return _run(
            "list_sources",
            lambda: with_conn(lambda conn: tools.list_sources(conn, settings)),
            lambda o: f"{o['project']} {o['version']} · {o['pages']} pages · {o['chunks']} chunks",
        )

    @server.tool(description=SEARCH_DOCS_DESC)
    @traceable(name="search_docs", run_type="tool")
    def search_docs(query: str, k: int = 5) -> dict[str, Any]:
        def summary(o: dict) -> str:
            best = "none" if o["best_distance"] is None else f"{o['best_distance']:.3f}"
            in_corpus = "yes" if o["in_corpus"] else "no"
            return f"{_plural(len(o['results']), 'result')} · best={best} · in_corpus={in_corpus}"

        return _run(
            f'search_docs query="{_short_query(query)}" k={max(tools.MIN_K, min(tools.MAX_K, k))}',
            lambda: with_conn(lambda conn: tools.search_docs(conn, client_factory(), settings, query, k)),
            summary,
        )

    @server.tool(description=GET_SECTION_DESC)
    @traceable(name="get_section", run_type="tool")
    def get_section(url: str) -> dict[str, Any]:
        return _run(
            f"get_section url={url.strip()}",
            lambda: with_conn(lambda conn: tools.get_section(conn, settings, url)),
            lambda o: f"1 section · {len(o['content'])} chars",
        )

    return server
