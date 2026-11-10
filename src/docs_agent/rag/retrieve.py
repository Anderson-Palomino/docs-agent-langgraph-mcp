"""Recuperación top-k por distancia coseno sobre pgvector."""

from dataclasses import dataclass

import psycopg
from pgvector import Vector


@dataclass(frozen=True)
class RetrievedChunk:
    id: int
    url: str
    title: str
    content: str
    distance: float


def search(conn: psycopg.Connection, query_embedding: list[float], source_ref: str, k: int = 5) -> list[RetrievedChunk]:
    """Devuelve los k fragmentos más cercanos de `source_ref` (distancia coseno `<=>`, menor = más similar)."""
    vec = Vector(query_embedding)
    rows = conn.execute(
        "SELECT id, url, title, content, embedding <=> %s AS distance"
        " FROM chunks WHERE source_ref = %s ORDER BY embedding <=> %s LIMIT %s",
        (vec, source_ref, vec, k),
    ).fetchall()
    return [RetrievedChunk(*row) for row in rows]


def corpus_size(conn: psycopg.Connection, source_ref: str) -> int:
    return conn.execute("SELECT count(*) FROM chunks WHERE source_ref = %s", (source_ref,)).fetchone()[0]


def corpus_stats(conn: psycopg.Connection, source_ref: str) -> tuple[int, int, int]:
    """(páginas, fragmentos, secciones) de `source_ref`; páginas = URLs sin ancla distintas."""
    return conn.execute(
        "SELECT (SELECT count(DISTINCT split_part(url, '#', 1)) FROM chunks WHERE source_ref = %s),"
        " (SELECT count(*) FROM chunks WHERE source_ref = %s),"
        " (SELECT count(*) FROM sections WHERE source_ref = %s)",
        (source_ref, source_ref, source_ref),
    ).fetchone()


def fetch_section(conn: psycopg.Connection, source_ref: str, url: str) -> tuple[str, str, str] | None:
    """(url, título, contenido) de la sección con esa URL exacta, o None."""
    return conn.execute(
        "SELECT url, title, content FROM sections WHERE source_ref = %s AND url = %s",
        (source_ref, url),
    ).fetchone()


def page_sections(conn: psycopg.Connection, source_ref: str, page_url: str) -> list[tuple[str, str]]:
    """(título, url) de las secciones con ancla de una página, en orden de documento."""
    return conn.execute(
        "SELECT title, url FROM sections WHERE source_ref = %s AND split_part(url, '#', 1) = %s"
        " AND url <> %s ORDER BY id",
        (source_ref, page_url, page_url),
    ).fetchall()
