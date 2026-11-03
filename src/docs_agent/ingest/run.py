"""Comando de ingesta: `python -m docs_agent.ingest.run`."""

import sys

import psycopg
from openai import OpenAI

from docs_agent.budget import KIND_INGEST, record_usage
from docs_agent.config import Settings, get_settings
from docs_agent.db import connect
from docs_agent.ingest.chunk import chunk_document
from docs_agent.ingest.embed import embed_texts
from docs_agent.ingest.fetch import fetch_docs
from docs_agent.ingest.store import replace_corpus


class IngestLimitExceeded(Exception):
    def __init__(self, estimate: int, limit: int):
        super().__init__(
            f"estimated {estimate} tokens exceeds INGEST_MAX_TOKENS={limit}; aborting before calling OpenAI"
        )
        self.estimate = estimate
        self.limit = limit


def _ingest(settings: Settings, client, conn: psycopg.Connection) -> tuple[int, int]:
    docs = fetch_docs(settings.fastapi_docs_ref)
    chunks = [
        c
        for doc in docs
        for c in chunk_document(
            doc, settings.chunk_max_tokens, settings.chunk_overlap_tokens
        )
    ]
    estimate = sum(c.token_count for c in chunks)
    if estimate > settings.ingest_max_tokens:
        raise IngestLimitExceeded(estimate, settings.ingest_max_tokens)
    embeddings, tokens = embed_texts(
        client, [c.content for c in chunks], settings.embedding_model
    )
    replace_corpus(conn, settings.fastapi_docs_ref, chunks, embeddings)
    record_usage(conn, KIND_INGEST, tokens)
    return len(chunks), tokens


def run_ingest(settings: Settings, client, conn: psycopg.Connection) -> int:
    """fetch -> chunk -> tope -> embed -> guardar -> registrar uso; devuelve nº de fragmentos."""
    return _ingest(settings, client, conn)[0]


def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        print("error: OPENAI_API_KEY is empty; set it in .env", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=settings.openai_api_key)
    conn = connect(settings.database_url)
    try:
        n, tokens = _ingest(settings, client, conn)
    except IngestLimitExceeded as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()
    print(
        f"Ingested {n} chunks from fastapi@{settings.fastapi_docs_ref} "
        f"({tokens} tokens)"
    )


if __name__ == "__main__":
    main()
