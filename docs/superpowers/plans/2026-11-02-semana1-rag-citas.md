# Semana 1 — RAG con citas: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docker compose up` levanta Postgres+pgvector y una API FastAPI cuyo `POST /ask` responde preguntas sobre la doc de FastAPI citando URLs reales de `fastapi.tiangolo.com`.

**Architecture:** Un comando de ingesta descarga los Markdown de `docs/en/docs/` de un tag fijo de `fastapi/fastapi`, los parte por encabezados, los embebe con `text-embedding-3-small` y los guarda en una tabla pgvector. `/ask` embebe la pregunta, trae el top-5 por coseno, pide a `gpt-4.1-mini` una salida estructurada `{answer, citations}` y descarta citas que no vengan de los fragmentos recuperados. Todo con el SDK de OpenAI y psycopg directos (sin LangChain).

**Tech Stack:** Python 3.12 (uv), FastAPI, uvicorn, openai, psycopg 3 + pgvector-python, pydantic-settings, tiktoken, httpx, pytest; Postgres + pgvector en Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-02-semana1-rag-citas-design.md`

## Global Constraints

- Python `>=3.12,<3.13` gestionado por uv (`uv python install 3.12`); la imagen Docker usa `python:3.12-slim` y el mismo `uv.lock`.
- Modelos: chat `gpt-4.1-mini`, embeddings `text-embedding-3-small` (dimensión 1536).
- Corpus: solo `docs/en/docs/**/*.md` de `fastapi/fastapi` en el tag de `FASTAPI_DOCS_REF`. Solo datos públicos.
- `top_k = 5`.
- Ningún test llama a la API real de OpenAI. Los tests que necesitan Postgres llevan `@pytest.mark.integration` y se saltan (skip, no fail) si la DB no responde.
- Postgres se expone en el host en **`localhost:5434`** (evita chocar con Postgres locales en 5432 y 5433). Dentro de compose: `db:5432`.
- Secretos solo en `.env` (en `.gitignore`); `.env.example` sin valores reales.
- Identidad git ya configurada en el repo. Cada commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commits pequeños, mensajes en inglés estilo conventional commits.
- Cada decisión técnica no trivial que tome el implementador → nueva entrada en `docs/decisiones.md` (formato: Elegido · Alternativas · Por qué), numerada a continuación de D12.
- Comandos de test: `uv run pytest -q` (unitarios + integración si la DB está arriba).

## Review Focus

1. **Corpus vacío** (no se corrió la ingesta) → `/ask` responde 503 con `"Corpus is empty: run the ingest command first"`, no un 500 ni una respuesta inventada. Test en Task 8.
2. **Pregunta vacía, solo espacios o > 1000 caracteres** → 422. Test en Task 8.
3. **Líneas `# ...` dentro de bloques de código** (comentarios de Python/bash) no se tratan como encabezados al trocear. Test en Task 4.
4. **Fallo de OpenAI** (excepción `openai.APIError` en embed o chat) → 502 `"Upstream model error"`, sin registrar uso. Test en Task 8.
5. **Presupuesto justo en el límite** (`used >= limit`) → 429; el chequeo es previo a la llamada, así que una petición puede pasarse por su propio costo (documentarlo en decisiones.md). Test en Task 5.

---

### Task 1: Scaffold del proyecto y configuración

**Files:**
- Create: `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example`, `src/docs_agent/__init__.py`, `src/docs_agent/config.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `docs_agent.config.Settings(BaseSettings)` con campos (env var en mayúsculas, lee `.env`):
    `openai_api_key: str = ""`, `database_url: str = "postgresql://docs:docs@localhost:5434/docs"`,
    `chat_model: str = "gpt-4.1-mini"`, `embedding_model: str = "text-embedding-3-small"`,
    `fastapi_docs_ref: str` (default = último tag estable de fastapi/fastapi al construir; resuélvelo con `gh api repos/fastapi/fastapi/releases/latest --jq .tag_name`),
    `top_k: int = 5`, `chunk_max_tokens: int = 800`, `chunk_overlap_tokens: int = 100`,
    `ask_daily_token_budget: int = 200_000`, `ingest_max_tokens: int = 2_000_000`.
  - `docs_agent.config.get_settings() -> Settings` (cacheado con `lru_cache`).
  - `tests/conftest.py`: fixture `settings_factory` → función `(**overrides) -> Settings(_env_file=None, **overrides)`. Registrar el marker `integration` en `pyproject.toml` (`[tool.pytest.ini_options] markers`).

- [ ] **Step 1:** Instalar uv a nivel de usuario (`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`), luego `uv python install 3.12`. Verificar: `uv --version` imprime versión.
- [ ] **Step 2:** `uv init --package --name docs-agent --python 3.12` (layout `src/docs_agent`), añadir deps: `uv add fastapi "uvicorn[standard]" openai "psycopg[binary]" pgvector pydantic-settings tiktoken httpx` y `uv add --dev pytest`. `.gitignore` incluye `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `data/`.
- [ ] **Step 3: Test que falla** — `tests/test_config.py`:

```python
def test_defaults(monkeypatch):
    monkeypatch.delenv("TOP_K", raising=False)
    s = Settings(_env_file=None)
    assert s.top_k == 5
    assert s.chat_model == "gpt-4.1-mini"
    assert s.embedding_model == "text-embedding-3-small"
    assert "localhost:5434" in s.database_url

def test_env_override(monkeypatch):
    monkeypatch.setenv("ASK_DAILY_TOKEN_BUDGET", "123")
    assert Settings(_env_file=None).ask_daily_token_budget == 123
```

- [ ] **Step 4:** `uv run pytest tests/test_config.py -q` → FAIL (ImportError).
- [ ] **Step 5:** Implementar `config.py` y `conftest.py`. `.env.example` lista todas las variables con valores de ejemplo y `OPENAI_API_KEY=sk-...`.
- [ ] **Step 6:** `uv run pytest -q` → PASS.
- [ ] **Step 7:** Añadir D13 en `docs/decisiones.md`: tag de FastAPI elegido y por qué; puerto 5434. Commit `chore: scaffold project with uv and settings`.

---

### Task 2: Postgres + pgvector en Docker Compose y esquema

**Files:**
- Create: `docker-compose.yml` (solo servicio `db` por ahora), `db/init.sql`, `src/docs_agent/db.py`, `tests/test_db.py`

**Interfaces:**
- Consumes: `get_settings()`.
- Produces:
  - Tablas: `chunks(id bigserial pk, source_ref text not null, url text not null, title text not null, content text not null, token_count int not null, embedding vector(1536) not null, created_at timestamptz default now())`; índice `chunks_embedding_hnsw` `USING hnsw (embedding vector_cosine_ops)`; índice btree en `source_ref`.
    `token_usage(day date not null, kind text not null, tokens bigint not null default 0, primary key(day, kind))`.
  - `docs_agent.db.connect(database_url: str | None = None) -> psycopg.Connection` — conecta (default `get_settings().database_url`), `register_vector(conn)`, devuelve la conexión (autocommit False).
  - `tests/conftest.py`: fixture `db_conn` — `connect()`; si falla, `pytest.skip("Postgres not available")`; antes y después del test hace `TRUNCATE chunks, token_usage` + commit; cierra al final.

- [ ] **Step 1:** Comprobar que Docker Desktop corre (`docker info`). Si no, pedir a Anderson que lo abra y esperar.
- [ ] **Step 2:** `docker-compose.yml`: servicio `db` con imagen `pgvector/pgvector:pg17`, env `POSTGRES_USER/PASSWORD/DB=docs`, puerto `5434:5432`, volumen nombrado `pgdata`, `./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro`, healthcheck `pg_isready -U docs`.
- [ ] **Step 3: Test que falla** — `tests/test_db.py` (`@pytest.mark.integration`):

```python
def test_vector_extension_and_tables(db_conn):
    rows = db_conn.execute("select extname from pg_extension where extname='vector'").fetchall()
    assert rows
    tables = {r[0] for r in db_conn.execute(
        "select tablename from pg_tables where schemaname='public'")}
    assert {"chunks", "token_usage"} <= tables

def test_embedding_dimension_is_1536(db_conn):
    dim = db_conn.execute(
        "select atttypmod from pg_attribute where attrelid='chunks'::regclass and attname='embedding'"
    ).fetchone()[0]
    assert dim == 1536
```

- [ ] **Step 4:** `uv run pytest tests/test_db.py -q` con la DB apagada → SKIPPED; luego escribir `init.sql`, `docker compose up -d db`, esperar healthy.
- [ ] **Step 5:** Implementar `db.py`. `uv run pytest -q` → PASS (integración incluida, no skipped).
- [ ] **Step 6:** Commit `feat: add postgres+pgvector schema and compose db service`. (Parámetros HNSW por defecto → D14 si se cambian.)

---

### Task 3: Descarga de la doc y mapeo a URLs/anclas

**Files:**
- Create: `src/docs_agent/ingest/__init__.py`, `src/docs_agent/ingest/fetch.py`, `tests/ingest/__init__.py`, `tests/ingest/test_fetch.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) DocFile: rel_path: str; url: str; text: str` (`rel_path` relativo a `docs/en/docs/`, con `/`).
  - `BASE_URL = "https://fastapi.tiangolo.com/"`
  - `EXCLUDED: tuple[str, ...]` — patrones glob de páginas sin valor para Q&A (como mínimo `release-notes.md`, `management*.md`, `fastapi-people.md`, `contributing.md`, `external-links.md`, `newsletter.md`, `help-fastapi.md`, `translation-banner.md`; ajustar mirando el árbol real del tag y anotar en decisiones.md).
  - `path_to_url(rel_path: str) -> str` — `"tutorial/body.md"` → `BASE_URL + "tutorial/body/"`; `"index.md"` → `BASE_URL`; `"advanced/index.md"` → `BASE_URL + "advanced/"`.
  - `heading_anchor(heading_text: str) -> tuple[str, str]` — devuelve `(title_limpio, anchor)`. Si el texto termina en `{ #algo }` (attr_list, usado en la doc de FastAPI) usa `algo` y quita el bloque del título; si no, slug estilo MkDocs `toc`: minúsculas, quitar caracteres no `[\w\s-]`, espacios→`-`.
  - `fetch_docs(ref: str, cache_dir: Path = Path("data")) -> list[DocFile]` — descarga `https://codeload.github.com/fastapi/fastapi/tar.gz/refs/tags/{ref}` con httpx (cachea el tarball en `cache_dir/fastapi-{ref}.tar.gz`), extrae en memoria solo `*/docs/en/docs/**/*.md`, aplica `EXCLUDED`, devuelve ordenado por `rel_path`.
  - `_docs_from_tarball(data: bytes) -> list[DocFile]` — la parte pura, testeable.

- [ ] **Step 1: Tests que fallan** — `tests/ingest/test_fetch.py`:

```python
@pytest.mark.parametrize("rel,url", [
    ("index.md", "https://fastapi.tiangolo.com/"),
    ("tutorial/body.md", "https://fastapi.tiangolo.com/tutorial/body/"),
    ("advanced/index.md", "https://fastapi.tiangolo.com/advanced/"),
])
def test_path_to_url(rel, url):
    assert path_to_url(rel) == url

def test_heading_anchor_explicit_id():
    assert heading_anchor("Request Body { #request-body }") == ("Request Body", "request-body")

def test_heading_anchor_slugified():
    assert heading_anchor("Import `BaseModel`!") == ("Import `BaseModel`!", "import-basemodel")

def test_tarball_filters_language_and_exclusions(tmp_path):
    data = make_tarball({  # helper en el test: arma un tar.gz en memoria
        "fastapi-0.0.0/docs/en/docs/tutorial/body.md": "# Body",
        "fastapi-0.0.0/docs/en/docs/release-notes.md": "# Notes",
        "fastapi-0.0.0/docs/es/docs/tutorial/body.md": "# Cuerpo",
        "fastapi-0.0.0/README.md": "x",
    })
    docs = _docs_from_tarball(data)
    assert [d.rel_path for d in docs] == ["tutorial/body.md"]
    assert docs[0].url == "https://fastapi.tiangolo.com/tutorial/body/"
```

- [ ] **Step 2:** `uv run pytest tests/ingest/test_fetch.py -q` → FAIL.
- [ ] **Step 3:** Implementar `fetch.py`.
- [ ] **Step 4:** Tests → PASS. Verificación manual: correr `fetch_docs(settings.fastapi_docs_ref)` una vez, imprimir cuántos archivos y 3 URLs con ancla; abrir esas 3 URLs (`curl -sI`) y confirmar 200 y que el ancla existe en el HTML (`curl -s URL | grep 'id="ancla"'`). Si los includes `{* ../../docs_src/... *}` aparecen en el texto, decidir dejarlos o resolverlos → D en decisiones.md.
- [ ] **Step 5:** Commit `feat(ingest): download fastapi docs and map files to public urls`.

---

### Task 4: Troceado por encabezados

**Files:**
- Create: `src/docs_agent/ingest/chunk.py`, `src/docs_agent/tokens.py`, `tests/ingest/test_chunk.py`

**Interfaces:**
- Consumes: `DocFile`, `heading_anchor`.
- Produces:
  - `docs_agent.tokens.count_tokens(text: str) -> int` — `tiktoken.get_encoding("cl100k_base")` (la codificación de `text-embedding-3-small`), encoder cacheado.
  - `@dataclass(frozen=True) Chunk: url: str; title: str; content: str; token_count: int`
  - `chunk_document(doc: DocFile, max_tokens: int = 800, overlap_tokens: int = 100) -> list[Chunk]`
    - Secciones: se corta en líneas `## ` y `### ` **fuera** de bloques ``` ``` ```. El texto antes del primer `##` forma una sección con `url = doc.url` (sin ancla) y título = H1 de la página (o `rel_path` si no hay H1).
    - Cada sección: `url = doc.url + "#" + anchor`, `title = f"{page_title} > {heading}"`, `content` incluye la línea del encabezado.
    - Secciones sin texto aparte del encabezado se omiten.
    - Si una sección supera `max_tokens`, se subdivide por párrafos (líneas en blanco, sin partir bloques de código) acumulando hasta `max_tokens`; cada sub-fragmento siguiente arranca con los últimos ~`overlap_tokens` del anterior. Todos los sub-fragmentos comparten `url` y `title`. Un único párrafo mayor que `max_tokens` se deja entero (no se parte a mitad de código).

- [ ] **Step 1: Tests que fallan** — `tests/ingest/test_chunk.py` (usa un `DocFile` de ejemplo):

```python
DOC = DocFile("tutorial/body.md", "https://fastapi.tiangolo.com/tutorial/body/",
    "# Request Body\n\nIntro text.\n\n## Import `BaseModel` { #import-basemodel }\n\n"
    "```python\n# this is a comment, not a heading\nfrom pydantic import BaseModel\n```\n\n"
    "### Create your data model\n\nDeclare it.\n")

def test_splits_on_h2_h3_and_keeps_intro():
    chunks = chunk_document(DOC)
    assert [c.url for c in chunks] == [
        "https://fastapi.tiangolo.com/tutorial/body/",
        "https://fastapi.tiangolo.com/tutorial/body/#import-basemodel",
        "https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model",
    ]
    assert chunks[1].title == "Request Body > Import `BaseModel`"

def test_comment_inside_code_fence_is_not_a_heading():
    chunks = chunk_document(DOC)
    assert "# this is a comment" in chunks[1].content
    assert len(chunks) == 3

def test_oversized_section_is_split_with_overlap():
    paras = [" ".join(f"p{p}w{i}" for i in range(60)) for p in range(8)]  # ~8 párrafos distintos
    doc = DocFile("a.md", "https://fastapi.tiangolo.com/a/", "# A\n\n## Big\n\n" + "\n\n".join(paras) + "\n")
    chunks = [c for c in chunk_document(doc, max_tokens=400, overlap_tokens=50) if c.url.endswith("#big")]
    assert len(chunks) >= 2
    assert all(c.token_count <= 400 + 50 for c in chunks)
    tail_of_first = chunks[0].content.split()[-5:]
    assert " ".join(tail_of_first) in chunks[1].content   # el 2º arranca con el final del 1º

def test_token_count_matches_counter():
    for c in chunk_document(DOC):
        assert c.token_count == count_tokens(c.content)
```

(El implementador puede reescribir la aserción de solapamiento del tercer test de forma más precisa, p. ej. comprobando que las primeras N palabras del fragmento 2 son las últimas N del fragmento 1.)

- [ ] **Step 2:** `uv run pytest tests/ingest/test_chunk.py -q` → FAIL.
- [ ] **Step 3:** Implementar `tokens.py` y `chunk.py`.
- [ ] **Step 4:** Tests → PASS.
- [ ] **Step 5:** Commit `feat(ingest): split markdown by headings with token cap and overlap`. Valores finales de tamaño/solapamiento → decisiones.md.

---

### Task 5: Presupuesto de tokens

**Files:**
- Create: `src/docs_agent/budget.py`, `tests/test_budget.py`

**Interfaces:**
- Consumes: `connect`, tabla `token_usage`.
- Produces:
  - `class BudgetExceeded(Exception)` con atributos `used: int`, `limit: int`.
  - `tokens_used_today(conn, kind: str) -> int` (día UTC; 0 si no hay fila).
  - `record_usage(conn, kind: str, tokens: int) -> None` — upsert `ON CONFLICT (day, kind) DO UPDATE SET tokens = token_usage.tokens + excluded.tokens`; hace commit.
  - `check_budget(conn, kind: str, limit: int) -> None` — lanza `BudgetExceeded` si `used >= limit`.
  - Constantes `KIND_ASK = "ask"`, `KIND_INGEST = "ingest"`.

- [ ] **Step 1: Tests que fallan** (`@pytest.mark.integration`):

```python
def test_record_accumulates(db_conn):
    record_usage(db_conn, KIND_ASK, 100); record_usage(db_conn, KIND_ASK, 50)
    assert tokens_used_today(db_conn, KIND_ASK) == 150
    assert tokens_used_today(db_conn, KIND_INGEST) == 0

def test_check_budget_at_limit_raises(db_conn):
    record_usage(db_conn, KIND_ASK, 1000)
    with pytest.raises(BudgetExceeded) as e:
        check_budget(db_conn, KIND_ASK, limit=1000)
    assert e.value.used == 1000 and e.value.limit == 1000

def test_check_budget_under_limit_ok(db_conn):
    record_usage(db_conn, KIND_ASK, 999)
    check_budget(db_conn, KIND_ASK, limit=1000)
```

- [ ] **Step 2:** Tests → FAIL. **Step 3:** Implementar. **Step 4:** Tests → PASS.
- [ ] **Step 5:** Añadir decisión (Review Focus #5: chequeo previo, posible sobrepaso de una petición; contabilidad en Postgres). Commit `feat: add daily token budget tracked in postgres`.

---

### Task 6: Embeddings, guardado y comando de ingesta

**Files:**
- Create: `src/docs_agent/ingest/embed.py`, `src/docs_agent/ingest/store.py`, `src/docs_agent/ingest/run.py`, `tests/ingest/test_embed.py`, `tests/ingest/test_store.py`, `tests/ingest/test_run.py`, `tests/fakes.py`

**Interfaces:**
- Consumes: `fetch_docs`, `chunk_document`, `Chunk`, `count_tokens`, `record_usage`, `KIND_INGEST`, `get_settings`, `connect`.
- Produces:
  - `tests/fakes.py`: `FakeOpenAI` con `.embeddings.create(model, input)` que devuelve objetos con `.data[i].embedding` (vector determinista de 1536 floats derivado del hash del texto, normalizado) y `.usage.total_tokens`; registra las llamadas en `.calls`. Lo reutilizan Tasks 7–8 (que le añaden `.chat.completions.parse`).
  - `embed_texts(client, texts: list[str], model: str, batch_size: int = 100) -> tuple[list[list[float]], int]` — vectores en el mismo orden + tokens totales de `usage`.
  - `replace_corpus(conn, source_ref: str, chunks: list[Chunk], embeddings: list[list[float]]) -> int` — en una transacción: `DELETE FROM chunks WHERE source_ref=%s` y luego insertar (usar `cursor.copy` o `executemany`); devuelve filas insertadas.
  - `class IngestLimitExceeded(Exception)`.
  - `run_ingest(settings: Settings, client, conn) -> int` — fetch → chunk (con `settings.chunk_*`) → `estimate = sum(c.token_count)`; si `estimate > settings.ingest_max_tokens` lanza `IngestLimitExceeded` **antes** de llamar a OpenAI → embed → `replace_corpus` → `record_usage(KIND_INGEST, tokens)`; devuelve nº de fragmentos.
  - `main()` en `run.py` (`python -m docs_agent.ingest.run`): construye settings/cliente/conexión, llama `run_ingest`, imprime `Ingested N chunks from fastapi@REF (T tokens)`; exit code 1 con mensaje claro en `IngestLimitExceeded` o si falta `OPENAI_API_KEY`.

- [ ] **Step 1: Tests que fallan:**

```python
# test_embed.py
def test_embed_batches_and_preserves_order():
    fake = FakeOpenAI()
    vecs, tokens = embed_texts(fake, [f"t{i}" for i in range(250)], model="m", batch_size=100)
    assert len(vecs) == 250 and len(fake.calls) == 3
    assert vecs[0] == fake.vector_for("t0") and tokens > 0

# test_store.py  (integration)
def test_replace_corpus_is_idempotent(db_conn):
    chunks = [Chunk("https://fastapi.tiangolo.com/a/#x", "A > X", "hello", 1)]
    vec = [[1.0] + [0.0] * 1535]
    assert replace_corpus(db_conn, "0.1", chunks, vec) == 1
    assert replace_corpus(db_conn, "0.1", chunks, vec) == 1
    assert db_conn.execute("select count(*) from chunks").fetchone()[0] == 1

# test_run.py  (integration; monkeypatch fetch_docs para devolver 1-2 DocFile pequeños)
def test_run_ingest_aborts_over_limit_without_calling_openai(db_conn, monkeypatch, settings_factory):
    fake = FakeOpenAI()
    with pytest.raises(IngestLimitExceeded):
        run_ingest(settings_factory(ingest_max_tokens=1), fake, db_conn)
    assert fake.calls == []

def test_run_ingest_stores_and_records_usage(db_conn, monkeypatch, settings_factory):
    n = run_ingest(settings_factory(), FakeOpenAI(), db_conn)
    assert n > 0
    assert tokens_used_today(db_conn, KIND_INGEST) > 0
```

(`settings_factory` viene de Task 1. `run.py` importa `fetch_docs` a nivel de módulo para que el test haga `monkeypatch.setattr("docs_agent.ingest.run.fetch_docs", lambda ref, **kw: [...])`.)

- [ ] **Step 2:** Tests → FAIL. **Step 3:** Implementar. **Step 4:** `uv run pytest -q` → PASS.
- [ ] **Step 5:** Commit `feat(ingest): embed chunks and store corpus with ingest token cap`.

---

### Task 7: Recuperación top-k

**Files:**
- Create: `src/docs_agent/rag/__init__.py`, `src/docs_agent/rag/retrieve.py`, `tests/rag/__init__.py`, `tests/rag/test_retrieve.py`

**Interfaces:**
- Consumes: `connect`, tabla `chunks`, `replace_corpus` (en el test).
- Produces:
  - `@dataclass(frozen=True) RetrievedChunk: id: int; url: str; title: str; content: str; distance: float`
  - `search(conn, query_embedding: list[float], k: int = 5) -> list[RetrievedChunk]` — `ORDER BY embedding <=> %s LIMIT %s`, `distance` = valor de `<=>`. Lista vacía si no hay filas.
  - `corpus_size(conn) -> int`.

- [ ] **Step 1: Test que falla** (integration):

```python
def unit(i):  # vector one-hot
    v = [0.0] * 1536; v[i] = 1.0; return v

def test_search_orders_by_cosine_distance(db_conn):
    chunks = [Chunk(f"https://fastapi.tiangolo.com/p{i}/", f"P{i}", f"c{i}", 1) for i in range(7)]
    replace_corpus(db_conn, "t", chunks, [unit(i) for i in range(7)])
    q = unit(3); q[4] = 0.5
    res = search(db_conn, q, k=5)
    assert len(res) == 5
    assert [r.url for r in res[:2]] == ["https://fastapi.tiangolo.com/p3/", "https://fastapi.tiangolo.com/p4/"]
    assert res[0].distance <= res[1].distance

def test_search_empty_corpus(db_conn):
    assert search(db_conn, unit(0)) == [] and corpus_size(db_conn) == 0
```

- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(rag): cosine top-k retrieval over pgvector`.

---

### Task 8: Respuesta con citas validadas y API `/ask`

**Files:**
- Create: `src/docs_agent/rag/answer.py`, `src/docs_agent/api.py`, `tests/rag/test_answer.py`, `tests/test_api.py`
- Modify: `tests/fakes.py` (añadir `chat.completions.parse`)

**Interfaces:**
- Consumes: `search`, `corpus_size`, `RetrievedChunk`, `embed_texts`, `check_budget`, `record_usage`, `BudgetExceeded`, `KIND_ASK`, `get_settings`, `connect`.
- Produces:
  - `class LLMAnswer(BaseModel): answer: str; citations: list[str]` (esquema de salida estructurada).
  - `class Citation(BaseModel): url: str; title: str`
  - `@dataclass AnswerResult: answer: str; citations: list[Citation]; grounded: bool; prompt_tokens: int; completion_tokens: int`
  - `build_messages(question: str, chunks: list[RetrievedChunk]) -> list[dict]` — system: responder **solo** con el contexto, en el **mismo idioma que la pregunta**, citar las URLs exactas de los fragmentos usados, y decir que no lo sabe si el contexto no alcanza; user: fragmentos numerados `[n] title\nURL: url\ncontent` + la pregunta.
  - `validate_citations(cited: list[str], chunks: list[RetrievedChunk]) -> list[Citation]` — mantiene solo URLs presentes en `chunks` (comparación exacta tras `strip()`), sin duplicados, en el orden citado; `title` del primer chunk con esa URL.
  - `answer_question(client, question: str, chunks: list[RetrievedChunk], model: str) -> AnswerResult` — `client.chat.completions.parse(model=model, messages=..., response_format=LLMAnswer, temperature=0)` (si la versión instalada del SDK expone `parse` solo bajo `client.beta`, usar esa y anotarlo); `grounded = len(citations) > 0`.
  - `api.py`: `app = FastAPI(title="docs-agent")`; dependencias `get_conn()` (yield de `connect()`, cierra al final) y `get_openai()` (`OpenAI(api_key=settings.openai_api_key)`), sobreescribibles en tests vía `app.dependency_overrides`.
    - `class AskRequest(BaseModel): question: str` — validador: `strip()`, 1..1000 caracteres → si no, 422.
    - `class AskResponse(BaseModel): answer: str; citations: list[Citation]; grounded: bool; usage: dict[str, int]` (`embedding_tokens`, `prompt_tokens`, `completion_tokens`); campo opcional `retrieved: list[dict] | None` (url, title, distance) solo si `?debug=true`.
    - `POST /ask`: `check_budget(KIND_ASK, settings.ask_daily_token_budget)` → 429 `{"detail": "Daily token budget exhausted"}`; si `corpus_size == 0` → 503 `"Corpus is empty: run the ingest command first"`; embed pregunta → `search(k=settings.top_k)` → `answer_question` → `record_usage(KIND_ASK, embedding+prompt+completion)` → 200. `openai.APIError` en embed o chat → 502 `"Upstream model error"` sin registrar uso.
    - `GET /health` → `{"status": "ok", "chunks": corpus_size}`; 503 si la DB no responde.

- [ ] **Step 1: Tests que fallan** — `tests/rag/test_answer.py` (unitarios, sin DB):

```python
CH = [RetrievedChunk(1, "https://fastapi.tiangolo.com/tutorial/body/#x", "Body > X", "...", 0.1),
      RetrievedChunk(2, "https://fastapi.tiangolo.com/tutorial/query/", "Query", "...", 0.2)]

def test_validate_drops_unknown_and_dedupes():
    cits = validate_citations(["https://fastapi.tiangolo.com/tutorial/body/#x", "https://evil.com/",
                               " https://fastapi.tiangolo.com/tutorial/body/#x "], CH)
    assert [c.url for c in cits] == ["https://fastapi.tiangolo.com/tutorial/body/#x"]
    assert cits[0].title == "Body > X"

def test_all_citations_dropped_is_not_grounded():
    fake = FakeOpenAI(parsed=LLMAnswer(answer="x", citations=["https://made.up/"]))
    r = answer_question(fake, "q", CH, model="m")
    assert r.citations == [] and r.grounded is False and r.answer == "x"

def test_messages_contain_numbered_chunks_and_language_rule():
    msgs = build_messages("¿Cómo declaro un body?", CH)
    joined = " ".join(m["content"] for m in msgs)
    assert "[1]" in joined and "https://fastapi.tiangolo.com/tutorial/query/" in joined
    assert "same language" in msgs[0]["content"].lower()
```

`tests/test_api.py` (integration; `TestClient` con overrides: `get_conn` → `db_conn`, `get_openai` → `FakeOpenAI`):

```python
def test_ask_happy_path(client, seeded_corpus):  # seeded_corpus: replace_corpus con 2 chunks
    r = client.post("/ask", json={"question": "How do I declare a body?"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True and body["citations"][0]["url"].startswith("https://fastapi.tiangolo.com/")
    assert set(body["usage"]) == {"embedding_tokens", "prompt_tokens", "completion_tokens"}

@pytest.mark.parametrize("q", ["", "   ", "x" * 1001])
def test_ask_rejects_bad_question(client, q):
    assert client.post("/ask", json={"question": q}).status_code == 422

def test_ask_empty_corpus_503(client):
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and "ingest" in r.json()["detail"]

def test_ask_budget_exhausted_429(client, seeded_corpus, db_conn, settings_factory):
    record_usage(db_conn, KIND_ASK, 10**9)
    assert client.post("/ask", json={"question": "hi"}).status_code == 429

def test_ask_upstream_error_502_and_no_usage(client_with_failing_openai, seeded_corpus, db_conn):
    r = client_with_failing_openai.post("/ask", json={"question": "hi"})
    assert r.status_code == 502
    assert tokens_used_today(db_conn, KIND_ASK) == 0

def test_ask_records_usage(client, seeded_corpus, db_conn):
    client.post("/ask", json={"question": "hi"})
    assert tokens_used_today(db_conn, KIND_ASK) > 0

def test_debug_includes_retrieved(client, seeded_corpus):
    assert client.post("/ask?debug=true", json={"question": "hi"}).json()["retrieved"]

def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
```

- [ ] **Step 2:** `uv run pytest tests/rag/test_answer.py tests/test_api.py -q` → FAIL.
- [ ] **Step 3:** Ampliar `FakeOpenAI` (`parsed=` configurable — por defecto cita la primera URL que aparezca en los mensajes —, `usage.prompt_tokens/completion_tokens`, modo `fail=True` que lanza `openai.APIError`). En `tests/conftest.py` añadir fixtures `client` (TestClient con overrides a `db_conn` y `FakeOpenAI()`), `client_with_failing_openai` (igual con `FakeOpenAI(fail=True)`) y `seeded_corpus` (`replace_corpus` con 2 chunks de URLs `fastapi.tiangolo.com` y vectores de `FakeOpenAI.vector_for`). Los tests de `test_api.py` llevan `@pytest.mark.integration`. Implementar `answer.py` y `api.py`.
- [ ] **Step 4:** `uv run pytest -q` → PASS.
- [ ] **Step 5:** Anotar en decisiones.md: conexión por petición (sin pool) en S1 y por qué; temperature 0; texto del prompt. Commit `feat(api): /ask with structured answer and validated citations`.

---

### Task 9: Imagen de la API, compose completo, smoke real y README

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `README.md`
- Modify: `docker-compose.yml` (servicio `api`), `docs/decisiones.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: `docker compose up` → `api` en `localhost:8000` (`DATABASE_URL=postgresql://docs:docs@db:5432/docs`, `env_file: .env`, `depends_on: db: condition: service_healthy`); ingesta con `docker compose run --rm api python -m docs_agent.ingest.run`.

- [ ] **Step 1:** `Dockerfile`: `python:3.12-slim`, copiar uv desde `ghcr.io/astral-sh/uv` (versión fijada), `uv sync --frozen --no-dev`, `CMD uvicorn docs_agent.api:app --host 0.0.0.0 --port 8000`. `.dockerignore` excluye `.venv`, `.env`, `data`, `.git`.
- [ ] **Step 2:** `docker compose build && docker compose up -d` → `curl -s localhost:8000/health` devuelve `{"status":"ok","chunks":0}`; `curl -s -X POST localhost:8000/ask -H 'content-type: application/json' -d '{"question":"hi"}'` devuelve 503.
- [ ] **Step 3:** Verificar que `.env` existe con `OPENAI_API_KEY` (pedírselo a Anderson si falta; **nunca** leer ni imprimir la key). Correr la ingesta real. Esperado: `Ingested N chunks ...` con N en cientos/miles; `/health` muestra `chunks: N`.
- [ ] **Step 4:** Smoke con 5 preguntas (≥1 en español), p. ej.:
  1. "How do I declare a request body with Pydantic?"
  2. "How can I run code before the application starts and after it shuts down?"
  3. "How do I return a custom status code from a path operation?"
  4. "¿Cómo agrego CORS a mi aplicación FastAPI?"
  5. "How do dependencies with yield work?"
  Para cada una: 200, `grounded: true`, y abrir cada URL citada (`curl -sI` → 200) y comprobar a ojo que la sección citada trata del tema. Si alguna falla, ajustar (prompt/troceado) con un ciclo de test, y anotarlo.
- [ ] **Step 5:** `README.md` en inglés: qué es (Week 1 of 4), arquitectura en 5 líneas, requisitos, quickstart (`cp .env.example .env`, `docker compose up -d`, comando de ingesta, `curl` de ejemplo), variables de entorno incluidos los dos límites de tokens, cómo correr tests, las 5 preguntas con respuesta y citas **reales** (salida recortada), link a `docs/decisiones.md`.
- [ ] **Step 6:** `uv run pytest -q` → todo PASS (integración no skipped con compose arriba). Commit `feat: dockerize api, add README with real example answers`.

---

## Verificación final (antes del code review)

- [ ] `docker compose down -v && docker compose up -d` + ingesta + 1 pregunta funciona desde cero.
- [ ] `uv run pytest -q` en verde, sin skips de integración.
- [ ] `git grep -i "sk-"` no encuentra keys; `.env` no está trackeado.
- [ ] `docs/decisiones.md` tiene D1–D12 + las nuevas de la ejecución.
