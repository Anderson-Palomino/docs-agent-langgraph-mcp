# docs-agent

A RAG agent that answers questions about the FastAPI documentation and **cites the exact doc section** it used. This is **Week 1 of 4** of a portfolio project (FastAPI + pgvector); later weeks add an agent loop (LangGraph), an MCP server and evaluations.

## Architecture

1. **Ingest** downloads the `docs/en/docs/**/*.md` of `fastapi/fastapi` at a pinned tag and splits it by `##`/`###` sections (max 800 tokens, 100 overlap), each with its own `#anchor` URL.
2. Chunks are embedded with `text-embedding-3-small` (1536 dims) and stored in Postgres + pgvector.
3. `POST /ask` embeds the question and retrieves the top 5 chunks by cosine similarity.
4. `gpt-4.1-mini` answers using only that context and returns structured `{answer, citations}`.
5. Cited URLs are validated against the retrieved chunks; invented ones are dropped (`grounded: false` if none survive). Daily token budgets cap the cost.

## Requirements

- Docker (with Compose) and an OpenAI API key.
- For tests: [uv](https://docs.astral.sh/uv/) (Python 3.12 is managed by uv).

## Quickstart

```bash
cp .env.example .env              # then put your OPENAI_API_KEY in .env
docker compose up -d              # db (localhost:5434) + api (localhost:8000)
docker compose run --rm api python -m docs_agent.ingest.run   # one-off corpus ingest
curl -s localhost:8000/health
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"How do I declare a request body with Pydantic?"}'
```

Add `?debug=true` to `/ask` to also get the retrieved chunks.

## Configuration

Environment variables (or `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | - | Required for ingest and `/ask` |
| `DATABASE_URL` | `postgresql://docs:docs@localhost:5434/docs` | Overridden to `db:5432` inside compose |
| `CHAT_MODEL` | `gpt-4.1-mini` | Answer model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `FASTAPI_DOCS_REF` | `0.162.0` | FastAPI tag to ingest |
| `TOP_K` | `5` | Chunks retrieved per question |
| `CHUNK_MAX_TOKENS` / `CHUNK_OVERLAP_TOKENS` | `800` / `100` | Chunking |
| `ASK_DAILY_TOKEN_BUDGET` | `200000` | Max tokens/day (UTC) spent by `/ask`; beyond it, HTTP 429 |
| `INGEST_MAX_TOKENS` | `2000000` | Ingest aborts before embedding if the corpus exceeds this |

## Tests

```bash
docker compose up -d db
uv run pytest -q
```

No test calls OpenAI. Integration tests need the compose db and are skipped if it is unreachable. They truncate the tables, so re-run the ingest afterwards.

## Example questions

<!-- EXAMPLES -->

## Design decisions

See [docs/decisiones.md](docs/decisiones.md) (in Spanish).
