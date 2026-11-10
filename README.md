# docs-agent

A RAG agent that answers questions about the FastAPI documentation and **cites the exact doc section** it used. This is **Week 2 of 4** of a portfolio project: Week 1 built the RAG API (FastAPI + pgvector); Week 2 turns `/ask` into a LangGraph agent that reads the corpus through its own MCP server, which Claude can also use (below). Evaluations come later.

## Architecture

1. **Ingest** downloads the `docs/en/docs/**/*.md` of `fastapi/fastapi` at a pinned tag and splits it by `##`/`###` sections (max 800 tokens, 100 overlap), each with its own `#anchor` URL.
2. Chunks are embedded with `text-embedding-3-small` (1536 dims) and stored in Postgres + pgvector.
3. `POST /ask` runs a LangGraph graph: a classifier (`gpt-4.1-mini`) sends out-of-domain questions straight to a fixed "no sé"; otherwise the graph calls the MCP server (`search_docs`, one persistent stdio session), which embeds the question and returns the top 5 chunks by cosine similarity. If the best distance is above the threshold (D21), the answer is "no sé" too.
4. Otherwise the graph reads the best hit's full section with `get_section`, and `gpt-4.1-mini` answers using only that section and the full top-k chunks, returning structured `{answer, citations}`.
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

**Upgrading from Week 1:** Postgres only runs `db/init.sql` on a new volume (D14), so an existing Docker volume lacks the `sections` table that `get_section` reads. Apply it (idempotent) and re-ingest:

```bash
docker compose exec -T db psql -U docs -d docs < db/init.sql
docker compose run --rm api python -m docs_agent.ingest.run
```

Until then, `get_section` fails and the graph answers from the search chunks alone (it logs a warning).

## Configuration

Environment variables (or `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | - | Required for ingest and `/ask` |
| `DATABASE_URL` | `postgresql://docs:docs@127.0.0.1:5434/docs` | Overridden to `db:5432` inside compose |
| `CHAT_MODEL` | `gpt-4.1-mini` | Answer model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `FASTAPI_DOCS_REF` | `0.162.0` | FastAPI tag to ingest |
| `TOP_K` | `5` | Chunks retrieved per question |
| `CHUNK_MAX_TOKENS` / `CHUNK_OVERLAP_TOKENS` | `800` / `100` | Chunking |
| `ASK_DAILY_TOKEN_BUDGET` | `200000` | Max tokens/day (UTC) spent by `/ask`; beyond it, HTTP 429 |
| `INGEST_MAX_TOKENS` | `2000000` | Ingest aborts before embedding if the corpus exceeds this |
| `NO_ANSWER_DISTANCE_THRESHOLD` | `0.52` | Best cosine distance above which the graph answers "no sé" (D21) |
| `MCP_BUDGET_SCOPE` / `MCP_DAILY_TOKEN_BUDGET` | `mcp` / `100000` | Which budget the MCP server spends (`mcp` when Claude launches it, `ask` when the API does) and its daily cap (D29) |
| `MCP_CALL_TIMEOUT_S` | `15` | Per-call timeout of the graph's MCP client; the server's OpenAI timeout is derived from it (D30) |
| `PRICE_CHAT_INPUT_PER_MTOK` / `PRICE_CHAT_OUTPUT_PER_MTOK` / `PRICE_EMBEDDING_PER_MTOK` | `0.40` / `1.60` / `0.02` | USD per million tokens, used by `scripts/demo_check.py` to report cost |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | `false` / - / `docs-agent` | Optional tracing (see below) |

## Agent graph

`POST /ask` runs a LangGraph graph (`src/docs_agent/agent/graph.py`). A classifier node routes out-of-domain questions straight to a fixed "no sé" answer; otherwise the graph searches the corpus through the MCP server, checks the best cosine distance against the threshold (D21) and either answers with citations or says it does not know. The diagram below is generated, not drawn by hand:

```bash
uv run python scripts/export_mermaid.py
```

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	classify(classify)
	search(search)
	evaluate(evaluate)
	answer(answer)
	no_se(no_se)
	__end__([<p>__end__</p>]):::last
	__start__ --> classify;
	classify -.-> no_se;
	classify -.-> search;
	evaluate -.-> answer;
	evaluate -.-> no_se;
	search --> evaluate;
	answer --> __end__;
	no_se --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

The response keeps the Week 1 fields and adds `route` (`answer` | `no_se`) and `reason` (`null` | `out_of_domain` | `insufficient_context`). See D32 and D33 in `docs/decisiones.md`.

## MCP server

`docs-agent-mcp` (stdio, `python -m docs_agent.mcp_server`) exposes the indexed corpus as three read-only tools:

| Tool | What it does |
|---|---|
| `list_sources` | Describes the corpus: project, docs version, number of pages, chunks and sections |
| `search_docs` | Semantic top-k search (k clamped to 1..10); returns title, url, distance, snippet, `best_distance` and `in_corpus`; `include_content=true` adds each chunk's full text (the graph uses it) |
| `get_section` | Full Markdown of one section by its exact URL (as returned by `search_docs`) |

Reasoning stays in the client (Claude, or the graph): the server only serves data (D27). Every call writes one line to **stderr** (stdout is the MCP channel), for example:

```text
[mcp] search_docs query="¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el…" k=5 → 5 results · best=0.461 · in_corpus=yes · 1190 ms
```

The server needs the compose db up and `OPENAI_API_KEY` in `.env` (read from the repo directory, so run it with `--directory <repo>`). `search_docs` spends embedding tokens against `MCP_BUDGET_SCOPE`: it defaults to `mcp` (own budget, `MCP_DAILY_TOKEN_BUDGET=100000`) when Claude launches the server; the API launches it with `ask` so the graph spends the `/ask` budget (D29).

### Connect from Claude Code

For the demo, open Claude Code **inside `demo/`**. That folder carries both halves of the setup:

- `demo/.mcp.json` registers the server (project scope, `uv --directory ..`), so Claude Code asks you to approve it the first time you run `claude` there.
- `demo/CLAUDE.md` is the **grounding policy**: for any technical question, call `docs-agent` first and answer only from what it returns; if `in_corpus=false` or the results only *mention* the topic, say so instead of answering from general knowledge.

```bash
cd demo
claude                 # approve "docs-agent" when prompted
claude mcp list        # docs-agent should show as Connected
```

To use the server from any other project instead (without the policy):

```bash
claude mcp add docs-agent --scope local -- uv --directory <repo> run python -m docs_agent.mcp_server
```

On Windows, for example `uv --directory C:/dev/docs-agent-langgraph-mcp ...`.

**Why the policy lives in the client (D35):** an MCP server offers tools; it cannot make the client use them. In rehearsal, without `demo/CLAUDE.md`, Claude judged the Django REST Framework question "not about FastAPI", never called `search_docs`, and answered from memory. With it: `search_docs` → `in_corpus=false` → an honest "the indexed docs don't cover this".

### Connect from Claude Desktop

Add this to `claude_desktop_config.json` and restart the app:

```json
{
  "mcpServers": {
    "docs-agent": {
      "command": "uv",
      "args": ["--directory", "<repo>", "run", "python", "-m", "docs_agent.mcp_server"]
    }
  }
}
```

Then create a **Project** in Claude Desktop and paste the paragraph from `demo/CLAUDE.md` as its project instructions: same server, same grounding policy (D35).

### Alongside the n8n MCP

The n8n workflow `integrations/n8n/workflows/02-mcp-docs-agent.json` exposes the whole agent as **one** HTTP tool (question in, answer with citations out), which suits flows and remote clients. This server exposes the **corpus** through three low-level tools so a client that reasons on its own (Claude, or the graph) can search, read the full section and decide. They solve different problems and coexist; `integrations/n8n/` is untouched. See D26.

## Tracing (optional)

Off by default; with it off nothing changes. To send traces to [LangSmith](https://smith.langchain.com/) (free Developer plan), set in `.env`:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...   # Personal Access Token; a write-only "Tracing Only" key is the least-privilege option (untested here)
LANGSMITH_PROJECT=docs-agent
```

Each `/ask` becomes an `ask` trace with the graph nodes and the OpenAI calls (tokens, latency, cost). The MCP server's tool calls appear as separate traces (no trace propagation over stdio). See D34 in `docs/decisiones.md`.

## Demo rehearsal

`scripts/demo_check.py` rehearses the 2-minute demo against the real MCP server (three moments: list sources, an OAuth2 question, an out-of-corpus Django REST Framework question), prints a pass/fail table and runs the test suite:

```bash
uv run python scripts/demo_check.py                          # moments 1-3 + pytest
uv run python scripts/demo_check.py --q "your question" --skip-tests
```

Exit codes: `0` all good, `1` a check or pytest failed (or server/model error), `2` budget exhausted. It needs the compose db with the ingested corpus and a valid `OPENAI_API_KEY`.

## Tests

```bash
docker compose up -d db
uv run pytest -q
```

206 tests. No test calls OpenAI. Integration tests need the compose db and are skipped if it is unreachable. They run against a separate `docs_test` database (created automatically on first run from `db/init.sql`; override by exporting `TEST_DATABASE_URL` in the shell; it is not read from `.env`), so the demo database `docs` is never touched.

## Example questions

Real outputs from `POST /ask` (corpus: FastAPI 0.162.0; answers trimmed to the first paragraph(s), `usage` omitted). Every cited URL returned HTTP 200 and the cited sections cover the topic. These were captured in **Week 1**, with the linear pipeline and a 1088-chunk corpus; the current corpus has 1128 chunks (D25), and Week 2 responses also carry `route` and `reason` (and `usage.classifier_tokens`), so the exact text and citations may differ.

**1. How do I declare a request body with Pydantic?**

> To declare a request body with Pydantic in FastAPI, you define a Pydantic model with the fields you expect in the request body. Then, you use this model as a parameter type in your path operation function. FastAPI will automatically recognize that this parameter should be taken from the request body and will validate and parse the incoming data accordingly.

`grounded: true`, citations:
  - [Request Body](https://fastapi.tiangolo.com/tutorial/body/)

**2. How can I run code before the application starts and after it shuts down?**

> You can run code before the application starts by defining logic that executes once before the application starts receiving requests. Similarly, you can run code after the application shuts down by defining logic that executes once after the application has finished handling requests. This is done using lifespan events in FastAPI, which cover the whole application lifespan. This approach is useful for setting up [...]

`grounded: true`, citations:
  - [Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)

**3. How do I return a custom status code from a path operation?**

> To return a custom status code from a path operation in FastAPI, you have a few options:
>
> 1. You can define the `status_code` parameter directly in your path operation decorator, passing either the integer code (e.g., `404`) or using the shortcut constants from `fastapi.status` or `starlette.status`.
>
> 2. If you need to return a different status code dynamically (not fixed in the decorator), you can declare a parameter of type `Response` in your path operation function. [...]

`grounded: true`, citations:
  - [Path Operation Configuration > Response Status Code](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#response-status-code)
  - [Response - Change Status Code > Use a `Response` parameter](https://fastapi.tiangolo.com/advanced/response-change-status-code/#use-a-response-parameter)

**4. ¿Cómo agrego CORS a mi aplicación FastAPI?**

> Para agregar CORS a tu aplicación FastAPI, debes usar el middleware `CORSMiddleware`. Los pasos son:
>
> 1. Importar `CORSMiddleware`.
> 2. Crear una lista de orígenes permitidos (como cadenas de texto). [...]

`grounded: true`, citations:
  - [CORS (Cross-Origin Resource Sharing) > Use `CORSMiddleware`](https://fastapi.tiangolo.com/tutorial/cors/#use-corsmiddleware)
  - [CORS (Cross-Origin Resource Sharing) > More info](https://fastapi.tiangolo.com/tutorial/cors/#more-info)

**5. How do dependencies with yield work?**

> Dependencies with `yield` in FastAPI allow you to run extra steps after finishing the main part of the dependency, often called "exit code" or "cleanup code". You write the main code up to the `yield` statement, which provides the value injected into path operations or other dependencies. The code after the `yield` is executed after the response is sent, allowing for cleanup actions like closing a database session.

`grounded: true`, citations:
  - [Dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
  - [Dependencies with yield > Sub-dependencies with `yield`](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#sub-dependencies-with-yield)
  - [Dependencies with yield > Execution of dependencies with `yield`](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#execution-of-dependencies-with-yield)
  - [Dependencies with yield > A database dependency with `yield`](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-database-dependency-with-yield)
  - [Advanced Dependencies > Dependencies with `yield` and `scope`](https://fastapi.tiangolo.com/advanced/advanced-dependencies/#dependencies-with-yield-and-scope)

Known weakness: answers are sometimes generic (question 2 explains the idea of lifespan events without showing the code), because the model is told to use only the retrieved fragments. Retrieval quality will be measured with evaluations in a later week.

## Design decisions

See [docs/decisiones.md](docs/decisiones.md) (in Spanish).
