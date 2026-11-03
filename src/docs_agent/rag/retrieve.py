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


def search(conn: psycopg.Connection, query_embedding: list[float], k: int = 5) -> list[RetrievedChunk]:
    """Devuelve los k fragmentos más cercanos (distancia coseno `<=>`, menor = más similar)."""
    vec = Vector(query_embedding)
    rows = conn.execute(
        "SELECT id, url, title, content, embedding <=> %s AS distance"
        " FROM chunks ORDER BY embedding <=> %s LIMIT %s",
        (vec, vec, k),
    ).fetchall()
    return [RetrievedChunk(*row) for row in rows]


def corpus_size(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
