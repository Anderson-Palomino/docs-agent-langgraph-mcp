"""Herramientas del servidor MCP como funciones puras sobre `conn` + cliente OpenAI (D26, D27).

No saben nada de MCP: `server.py` las envuelve, abre la conexión y escribe el log.
"""

import re

import psycopg

from docs_agent.budget import check_budget, record_usage
from docs_agent.config import Settings
from docs_agent.ingest.embed import embed_texts
from docs_agent.ingest.fetch import heading_anchor
from docs_agent.rag.retrieve import corpus_stats, fetch_section, page_sections, search

PROJECT = "FastAPI"
SNIPPET_CHARS = 300
MIN_K, MAX_K = 1, 10
NOT_IN_CORPUS_NOTICE = "No relevant section in the indexed FastAPI docs. Do not answer from general knowledge."

_HEADING_LINE = re.compile(r"^(#{1,6}) +(\S.*)$")


def list_sources(conn: psycopg.Connection, settings: Settings) -> dict:
    pages, chunks, sections = corpus_stats(conn, settings.fastapi_docs_ref)
    return {
        "project": PROJECT,
        "version": settings.fastapi_docs_ref,
        "pages": pages,
        "chunks": chunks,
        "sections": sections,
    }


def clamp_k(k: int) -> int:
    return max(MIN_K, min(MAX_K, k))


def _budget_limit(settings: Settings) -> int:
    if settings.mcp_budget_scope == "ask":
        return settings.ask_daily_token_budget
    return settings.mcp_daily_token_budget


def search_docs(conn: psycopg.Connection, client, settings: Settings, query: str, k: int = 5) -> dict:
    """Top-k fragmentos de la versión indexada. Lanza `BudgetExceeded` si el presupuesto del scope se agotó."""
    k = clamp_k(k)
    kind = settings.mcp_budget_scope
    check_budget(conn, kind, _budget_limit(settings))
    vectors, tokens = embed_texts(client, [query], settings.embedding_model)
    record_usage(conn, kind, tokens)  # antes de buscar: los tokens ya se gastaron aunque falle la consulta
    chunks = search(conn, vectors[0], settings.fastapi_docs_ref, k=k)
    best = float(chunks[0].distance) if chunks else None
    in_corpus = best is not None and best <= settings.no_answer_distance_threshold
    return {
        "results": [
            {
                "title": c.title,
                "url": c.url,
                "distance": round(float(c.distance), 4),
                "snippet": c.content[:SNIPPET_CHARS],
            }
            for c in chunks
        ],
        "best_distance": round(best, 4) if best is not None else None,
        "in_corpus": in_corpus,
        "notice": None if in_corpus else NOT_IN_CORPUS_NOTICE,
        "embedding_tokens": tokens,
    }


def _clean_heading(content: str) -> str:
    """Quita el sufijo attr_list (`{ #id }`) de la línea de encabezado inicial; el resto queda igual."""
    first, sep, rest = content.partition("\n")
    m = _HEADING_LINE.match(first)
    if not m:
        return content
    clean, _ = heading_anchor(m.group(2))
    return f"{m.group(1)} {clean}{sep}{rest}"


def get_section(conn: psycopg.Connection, settings: Settings, url: str) -> dict:
    """Sección completa por URL exacta. Una URL de página (sin ancla) trae la intro y el índice de secciones."""
    url = url.strip()
    ref = settings.fastapi_docs_ref
    row = fetch_section(conn, ref, url)
    if "#" in url:
        if row is None:
            raise LookupError(f"Unknown section URL: {url}. Use search_docs to find valid URLs.")
        _, title, content = row
        return {"url": url, "title": title, "content": _clean_heading(content)}

    subsections = page_sections(conn, ref, url)
    if row is None and not subsections:
        raise LookupError(f"Unknown section URL: {url}. Use search_docs to find valid URLs.")
    if row is not None:
        title, content = row[1], _clean_heading(row[2])
    else:  # página cuya intro no tiene cuerpo (solo el H1): no se guardó como sección
        title, content = subsections[0][0].split(" > ", 1)[0], ""
    return {
        "url": url,
        "title": title,
        "content": content,
        "sections": [{"title": t, "url": u} for t, u in subsections],
    }
