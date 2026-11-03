"""Guarda el corpus en Postgres reemplazando el de la misma versión."""

import psycopg
from pgvector import Vector

from docs_agent.ingest.chunk import Chunk


def replace_corpus(
    conn: psycopg.Connection,
    source_ref: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> int:
    """Borra e inserta en una sola transacción; devuelve las filas insertadas."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    rows = [
        (source_ref, c.url, c.title, c.content, c.token_count, Vector(e))
        for c, e in zip(chunks, embeddings, strict=True)
    ]
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE source_ref = %s", (source_ref,))
            cur.executemany(
                "INSERT INTO chunks (source_ref, url, title, content, token_count, embedding)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                rows,
            )
        # commit explícito: puede haber una transacción de lectura previa abierta,
        # en cuyo caso `conn.transaction()` sería solo un savepoint y no confirmaría.
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(rows)
