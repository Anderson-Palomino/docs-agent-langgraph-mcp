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
