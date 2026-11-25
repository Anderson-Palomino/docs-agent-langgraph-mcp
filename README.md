# docs-agent

A RAG agent that answers questions about the FastAPI documentation, in **Spanish or English**, and **cites the exact doc section** it used (or says "no sé" when the docs don't cover it). It is a LangGraph agent served by FastAPI that reads a Postgres/pgvector corpus through **its own MCP server**, which Claude can also use. Built as a 4-week portfolio project; every design decision is recorded in [docs/decisiones.md](docs/decisiones.md) (in Spanish).

## Try it live

Live demo: https://docs-agent-cqpr.onrender.com/docs (interactive API docs; `/` redirects there). It runs on Render's Free plan, so **the first request after ~15 minutes idle takes about a minute** (cold start). `/ask` is limited to 20 requests per hour per IP and to a daily token budget (D37); beyond either, HTTP 429.

Open `POST /ask` > "Try it out" and send one of these:

```json
{"question": "How do I declare a request body with Pydantic?"}
{"question": "¿Cómo agrego CORS a mi aplicación FastAPI?"}
{"question": "How do I protect a Django REST Framework view with permissions?"}
```

The first two return an answer with citations (the Spanish one is answered in Spanish); the third is out of the corpus and returns "no sé" (`route: "no_se"`).

## System overview

```mermaid
flowchart LR
    U[Client: curl / Swagger / n8n] --> API[FastAPI<br/>POST /ask]
    API --> G[LangGraph graph<br/>classify, search, evaluate, answer or no sé]
    G <-->|stdio MCP client| M[MCP server<br/>search_docs, get_section, list_sources]
    M --> PG[(Postgres + pgvector<br/>FastAPI docs chunks)]
    G --> O[OpenAI<br/>gpt-4.1-mini, text-embedding-3-small]
    M --> O
    C[Claude Code / Desktop] -->|stdio MCP| M
```

## Architecture

1. **Ingest** downloads the `docs/en/docs/**/*.md` of `fastapi/fastapi` at a pinned tag and splits it by `##`/`###` sections (max 800 tokens, 100 overlap), each with its own `#anchor` URL.
2. Chunks are embedded with `text-embedding-3-small` (1536 dims) and stored in Postgres + pgvector.
3. `POST /ask` runs a LangGraph graph: a classifier (`gpt-4.1-mini`) sends out-of-domain questions straight to a fixed "no sé" and, for Spanish questions, also translates the question into an English search query (D40; the answer is still written in the user's language); otherwise the graph calls the MCP server (`search_docs`, one persistent stdio session), which embeds the question and returns the top 5 chunks by cosine similarity. If the best distance is above the threshold (D21), the answer is "no sé" too.
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
| `ASK_RATE_LIMIT_PER_HOUR` | `20` | Max `/ask` requests per hour per client IP (sliding window, in memory: per instance, resets on deploy); beyond it, HTTP 429 with `Retry-After`. `0` disables it. `/health` is never limited. The counter is per process: with several workers the effective limit is limit x workers |
| `TRUSTED_PROXY_IPS` | _(empty)_ | Comma-separated IPs/CIDR of proxies whose `X-Forwarded-For` is trusted, or `*` (any peer). Empty = key by socket IP (fine locally and for n8n; behind a proxy every client would share one IP, so set it). The socket peer must be trusted for `X-Forwarded-For` to be read; then `TRUSTED_PROXY_HOPS` decides which entry is the client |
| `TRUSTED_PROXY_HOPS` | `2` | How many proxy hops sit at the right end of `X-Forwarded-For` (on Render: Cloudflare's edge and Render's internal hop). The client IP is the entry just before them, so anything a caller adds on the left is ignored. A chain shorter than expected (or a non-IP at that position) falls back to one shared bucket, `untrusted-chain`, and logs a throttled warning. `0` = legacy rule: the rightmost entry that is not a trusted proxy (D37) |
| `EVAL_DAILY_TOKEN_BUDGET` | `600000` | Max tokens/day (UTC) the evaluation script spends, in its own `eval` kind so it never eats the live `/ask` budget (D39) |
| `INGEST_MAX_TOKENS` | `2000000` | Ingest aborts before embedding if the corpus exceeds this |
| `NO_ANSWER_DISTANCE_THRESHOLD` | `0.52` | Best cosine distance above which the graph answers "no sé" (D21) |
| `MCP_BUDGET_SCOPE` / `MCP_DAILY_TOKEN_BUDGET` | `mcp` / `100000` | Which budget the MCP server spends (`mcp` when Claude launches it, `ask` when the API does, `eval` for the evaluation script) and its daily cap (D29, D39) |
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

## Evaluation

`scripts/evaluate.py` runs a golden set through the same path as `/ask` (real MCP server over stdio) and scores it. All runs: `gpt-4.1-mini`, judge `gpt-4.1-mini`, threshold 0.52, k=5, FastAPI docs 0.162.0, one run each.

### Holdout: the clean measurement (Spanish)

6 Spanish questions written before the translation prompt was frozen and never used to tune anything (`eval/holdout_es.json`; source: `eval/results/2026-11-25-holdout.md`). 4 are in the corpus and 2 are out of it (a Flask question and a cooking question).

| Metric | Value |
|---|---|
| Cases | 6 (6 without error) |
| Route accuracy | 66.7% (4/6) |
| Route matrix | answer ok 2, no_se ok 2, false "no sé" 2, false "answered" 0 |
| Classifier decision correct | 100.0% (6/6; 2 cut, 4 passed) |
| Source hit (at least one expected URL cited) | 100.0% (2/2) |
| Valid citations (grounded) | 100.0% (2/2) |
| Faithfulness (judge mean) | 1.00 (2 judged / 2 answered) |
| Graph latency p50 / p95 | 1,549 ms / 5,566 ms |
| Cost per question (incl. judge) | US$0.0011 |
| Run tokens | 11,688 |

Read it for what it is: 6 cases is far too few for a stable figure. In plain words, 2 of the 4 valid Spanish questions were answered, and nothing out of domain slipped through.

### Golden set: 30 cases (not a clean measurement)

The golden set (`eval/golden_set.json`, 15 of its cases in Spanish) is where the translation prompt was developed: **the prompt was adjusted once while looking at these cases** (D40), so the "after" column is optimistic. Sources: `eval/results/2026-11-17.md` (before translation) and `eval/results/2026-11-25-2.md` (after), side by side in `eval/results/2026-11-25-comparison.md`.

| Metric | Before (2026-11-17) | After (2026-11-25-2) |
|---|---|---|
| Cases | 30 (30 without error) | 30 (30 without error) |
| Route accuracy | 80.0% (24/30) | 90.0% (27/30) |
| Route matrix | answer ok 15, no_se ok 9, false "no sé" 4, false "answered" 2 | answer ok 18, no_se ok 9, false "no sé" 1, false "answered" 2 |
| Source hit (at least one expected URL cited) | 87.5% (14/16) | 84.2% (16/19) |
| Source hit, multi-source cases (all expected URLs cited) | 66.7% (2/3) | 66.7% (2/3) |
| Valid citations (grounded) | 88.2% (15/17) | 90.0% (18/20) |
| Faithfulness (judge mean) | 1.00 (17 judged) | 0.99 (20 judged) |
| Answers with some unsupported claim | 0.0% (0/17) | 5.0% (1/20) |
| Graph latency p50 / p95 | 3,261 ms / 5,412 ms | 3,418 ms / 5,948 ms |
| Cost per question (incl. judge) | US$0.0013 | US$0.0016 |
| Run tokens | 70,141 | 86,479 |

The 3 false "no sé" that were fixed (g03, g06, g07) are Spanish questions whose translated query landed closer to the right page (for example g06: distance 0.617 to 0.374).

```bash
uv run python scripts/evaluate.py                          # 30 cases, with judge
uv run python scripts/evaluate.py --only g01,g05 --no-judge
uv run python scripts/evaluate.py --golden eval/holdout_es.json
uv run python scripts/evaluate.py --golden path.json --max-tokens 200000
```

- It needs the compose db with the ingested corpus and a valid `OPENAI_API_KEY`; run it only against the local `docs` database. A full golden run is ~86k tokens, about US$0.05.
- Spend goes to its own budget kind, `eval` (`EVAL_DAILY_TOKEN_BUDGET`, D39), so it never eats the live `/ask` budget. `--max-tokens` (default 400,000) caps one run; it is checked before each case, so a run may overshoot it by at most one case.
- Outputs: `eval/results/<Lima day>.json` and `.md`; earlier runs are not overwritten. The sheet for manually reviewing the judge is built separately by `scripts/judge_review_sheet.py` (`evaluate.py` does not write it). Exit codes: `0` ok, `1` failure or a case with error, `2` budget.

What the metrics mean, and what they do not measure:

- **Route accuracy**: whether the graph answered or said "no sé" as the golden case expects. It says nothing about the quality of the answer.
- **Source hit / grounded**: the cited URLs (normalized) match `expected_urls`, and the citations come from what was retrieved. A right URL does not mean the text says what the answer claims.
- **Faithfulness**: an LLM judge lists each claim of the answer and checks it against the exact context the answering model saw (D38). It measures support in the context, not truth: an answer faithful to a wrong passage scores high. The judge is the same model as the answerer and may share its blind spots. **A manual review agreed with the judge on 56 of 56 claims (9 of 9 cases)** (`eval/results/2026-11-25-judge-review.md`, D38). The review also found the judge is strict with commands but lenient with rewritten code: it flags a shell command missing from the context, yet accepts code examples the model rewrote. So the mean of 0.99 (golden set after: 1 of 20 answers with an unsupported claim) means support in the context, not correct code.
- Every figure comes from a single run.

## Limitations

- **The holdout is tiny** (6 questions), so the Spanish numbers are indicative, not statistics.
- **Spanish sits farther from the corpus than English**, even after translation (D40): the corpus is English and the embedding model is not tuned for cross-language search. h02 (static files) landed at distance 0.523, just above the 0.52 threshold and was answered "no sé" by a hair.
- **h04 is a retrieval miss, not a threshold problem**: the right page (`header-params`) is not among the top two results, so no reasonable threshold fixes it (D41).
- **The classifier, not the threshold, is the defense for other-framework questions.** Translation adds "in FastAPI" to many queries, which pulls them closer to the corpus; g25 (pure Starlette, in Spanish) is already below 0.52 and would be answered if the classifier let it through.
- **The threshold stays at 0.52** (D41). Tuning it on the holdout would contaminate it; recalibration is planned for Week 5 with a new, unseen holdout.
- **The rate limiter is per instance and in memory**: it resets on deploy and, with several workers, the effective limit is limit x workers (D37). Its key is the client's public IP, taken two hops from the right of `X-Forwarded-For` (Cloudflare's edge and Render's internal hop); verified on Render on 2026-11-25: two networks got separate quotas and a spoofed left-hand entry did not change the key (D37).
- **Faithfulness is judged by the same model that answers**, and it does not check code the model rewrote (see above).

## Tests

```bash
docker compose up -d db
uv run pytest -q
```

No test calls OpenAI. Integration tests need the compose db and are skipped if it is unreachable. They run against a separate `docs_test` database (created automatically on first run from `db/init.sql`; override by exporting `TEST_DATABASE_URL` in the shell; it is not read from `.env`), so the demo database `docs` is never touched.

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

Known weakness: answers are sometimes generic (question 2 explains the idea of lifespan events without showing the code), because the model is told to use only the retrieved fragments. Retrieval quality is measured in the Evaluation section.

## Design decisions

See [docs/decisiones.md](docs/decisiones.md) (in Spanish).
