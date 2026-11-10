"""Guarda el corpus en Postgres reemplazando el de la misma versión."""

from collections.abc import Sequence

import psycopg
from pgvector import Vector

from docs_agent.ingest.chunk import Chunk, Section


def replace_corpus(
    conn: psycopg.Connection,
    source_ref: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    sections: Sequence[Section] = (),
) -> int:
    """Reemplaza chunks y sections del source_ref en una sola transacción; devuelve los chunks insertados.

    Omitir `sections` borra las secciones existentes del source_ref.
    """
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    rows = [
        (source_ref, c.url, c.title, c.content, c.token_count, Vector(e))
        for c, e in zip(chunks, embeddings, strict=True)
    ]
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE source_ref = %s", (source_ref,))
            cur.execute("DELETE FROM sections WHERE source_ref = %s", (source_ref,))
            cur.executemany(
                "INSERT INTO chunks (source_ref, url, title, content, token_count, embedding)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                rows,
            )
            cur.executemany(
                "INSERT INTO sections (source_ref, url, title, content) VALUES (%s, %s, %s, %s)",
                [(source_ref, x.url, x.title, x.content) for x in sections],
            )
        # commit explícito: puede haber una transacción de lectura previa abierta,
        # en cuyo caso `conn.transaction()` sería solo un savepoint y no confirmaría.
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(rows)
