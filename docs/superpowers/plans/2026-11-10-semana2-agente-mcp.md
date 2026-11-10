# Semana 2 — Agente LangGraph + servidor MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/ask` pasa a ser un grafo LangGraph que consume un servidor MCP propio (stdio, 3 herramientas) sobre un corpus re-ingestado con el código de `docs_src`, con tracing LangSmith opcional y un `demo_check.py` para ensayar la demo.

**Architecture:** La ingesta resuelve los includes `{* docs_src *}` y guarda fragmentos + secciones completas. Un servidor MCP (`MCPServer` del SDK oficial v2) expone `list_sources`/`search_docs`/`get_section` leyendo Postgres. El grafo (clasificar → buscar → evaluar → responder | no_se) llama a ese servidor a través de un cliente MCP de sesión única con reconexión y timeout; `/ask` (FastAPI) invoca el grafo.

**Tech Stack:** Python 3.12 (uv), FastAPI, psycopg 3 + pgvector, openai, **langgraph 1.2.x**, **mcp 2.3.x**, **langsmith 0.14.x**, **rich 15.x**, pytest (+ plugin `anyio` para tests async).

**Spec:** `docs/superpowers/specs/2026-11-10-semana2-agente-mcp-design.md` (léelo; manda sobre este plan).

## Global Constraints

- Rama `feat/semana2-agente-mcp`. Commits pequeños, mensajes en el estilo del repo (`feat(...)`, `fix(...)`, `docs(...)`, `test(...)`), identidad `Anderson-Palomino <170631001+Anderson-Palomino@users.noreply.github.com>`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **APIs verificadas (instaladas en un venv de prueba el 2026-11-10)** — usar exactamente estas; ante cualquier otra API, verificar en la doc oficial / `inspect.signature` de la versión instalada antes de usarla:
  - LangGraph 1.2.20: `from langgraph.graph import StateGraph, START, END`; `StateGraph(StateTypedDict)`, `.add_node(name, fn)`, `.add_edge(a, b)`, `.add_conditional_edges(source, path_fn, path_map)`, `.compile()`; `compiled.ainvoke(state)`; `compiled.get_graph().draw_mermaid()`.
  - MCP SDK 2.3.0 (API v2; **no** usar `FastMCP`/`mcp.server.fastmcp` de v1): servidor `from mcp.server import MCPServer`; `MCPServer(name, instructions=..., version=...)`; `@server.tool(description=...)`; `server.run("stdio")`. Cliente `from mcp import Client, StdioServerParameters`; `async with Client(params_or_server_instance) as c:`; `await c.call_tool(name, args, read_timeout_seconds=...)` → `CallToolResult` con `.structured_content`, `.content`, `.is_error`; `await c.list_tools()`. `Client(server_instance)` conecta en proceso (para tests). `StdioServerParameters(command=..., args=[...], env={...}, cwd=...)` — **`env` reemplaza el entorno heredado** (solo hereda unas pocas variables por defecto): pasar `{**os.environ, ...}` explícitamente.
  - LangSmith 0.14.17: `from langsmith import traceable`; `from langsmith.wrappers import wrap_openai`; variables `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. LangSmith lee `os.environ`, no `.env`.
- Postgres en `127.0.0.1:5434` (nunca `localhost`, D14). Base de la demo `docs`; base de tests `docs_test`.
- **Ningún test llama a OpenAI ni a LangSmith.** Los tests de integración usan solo `docs_test`.
- Presupuesto (`budget.py`) en todo camino que gasta tokens. `kind` nuevos: `mcp` (y el existente `ask`).
- `/ask` mantiene `answer`, `citations`, `grounded`, `usage` (claves actuales `embedding_tokens`, `prompt_tokens`, `completion_tokens`), `retrieved?` y los códigos 422/429/502/503; solo añade campos. `integrations/n8n/` no se toca.
- Valores fijos: `route ∈ {"answer", "no_se"}`; `reason ∈ {None, "out_of_domain", "insufficient_context"}`; `MCP_BUDGET_SCOPE ∈ {"mcp","ask"}` (default `mcp`); `MCP_DAILY_TOKEN_BUDGET=100000`; `CHUNK_MAX_TOKENS=800` **incluyendo el solape**.
- Agentes: nunca leer, imprimir ni editar `.env`. Encender Docker Desktop reinicia contenedores de otro proyecto (Supabase de MedicionHoras): si aparecen, detenerlos con `docker stop` (solo esos) y seguir.
- Decisiones en `docs/decisiones.md` (español, formato existente `### DNN. Título` + **Elegido / Alternativas / Por qué**). **D21 queda reservada al umbral** (Task 5); el resto toma D22, D23… en el orden en que se escriben.
- Hoy: 52 tests (23 unitarios + 29 integración). Las aserciones existentes no se debilitan; solo se ajusta el cableado de fixtures cuando el código nuevo lo exige.

## Review Focus

1. Pregunta con un include cuyo archivo no existe o con `ln[...]` fuera de rango → la ingesta no se cae; queda la línea `[code example: <ruta> not available]` y un conteo en el log (Task 2).
2. El proceso del servidor MCP muere o tarda → `/ask` responde 503 `"Docs server unavailable"` (no 500) y la siguiente pregunta funciona porque el cliente se reconecta (Tasks 7 y 9).
3. Servidor MCP lanzado por la API dentro de Docker sin variables (`DATABASE_URL`, `OPENAI_API_KEY`) → se las pasa la API vía `env={**os.environ, "MCP_BUDGET_SCOPE": "ask"}`; test que verifica los `StdioServerParameters` construidos (Task 9).
4. `get_section` con una URL desconocida o con espacios/ancla distinta → error claro que sugiere `search_docs`, no excepción cruda (Task 6).
5. Presupuesto agotado a mitad de camino (el clasificador pasa, `search_docs` lo rechaza) → `/ask` 429, sin registrar uso de lo que no se gastó (Tasks 8 y 9).

---

### Task 1: Base de tests separada (`docs_test`)

**Files:**
- Modify: `tests/conftest.py`, `src/docs_agent/config.py`, `.env.example`, `README.md` (sección Tests)
- Test: `tests/test_test_db.py`

**Interfaces:**
- Produces: `Settings.test_database_url: str = "postgresql://docs:docs@127.0.0.1:5434/docs_test"`; fixture autouse que fija `DATABASE_URL` = `TEST_DATABASE_URL` (env si está exportada, si no el default); fixture de sesión `_ensure_test_db` que crea `docs_test` si falta (conectando con autocommit a la base `postgres` del mismo servidor, `CREATE DATABASE docs_test`) y aplica `db/init.sql`; si Postgres no responde, no falla (los tests de integración se saltan como hoy).

- [ ] **Step 1:** Test `test_tests_never_point_at_demo_db`: dentro de un test, `get_settings().database_url` termina en `/docs_test`. Test de integración `test_db_conn_uses_test_database`: `db_conn.execute("select current_database()").fetchone()[0] == "docs_test"`.
- [ ] **Step 2:** Correr: `uv run pytest tests/test_test_db.py -v` → FAIL.
- [ ] **Step 3:** Implementar lo de Interfaces. `db_conn` sigue truncando, pero ahora solo `docs_test`.
- [ ] **Step 4:** Levantar la db (`docker compose up -d db`), anotar `select count(*) from chunks` en `docs` (base de la demo), correr `uv run pytest -q` → 54 passed, y verificar que el conteo de `docs` **no cambió**.
- [ ] **Step 5:** Decisión D22 "Base de tests separada" (por qué no un contenedor aparte ni testcontainers). Commit `test: base docs_test separada para no borrar la base de la demo`.

### Task 2: Resolver includes `docs_src`

**Files:**
- Create: `src/docs_agent/ingest/includes.py`
- Modify: `src/docs_agent/ingest/fetch.py` (leer también `docs_src/**` del tarball y aplicar la resolución a cada `DocFile.text`)
- Test: `tests/ingest/test_includes.py`

**Interfaces:**
- Produces: `resolve_includes(text: str, src_files: dict[str, str]) -> tuple[str, list[str]]` — devuelve (texto con cada `{* ../../docs_src/<ruta> [ln[...]] [hl[...]] *}` reemplazado por un bloque ```` ```python ```` , lista de rutas no resueltas). `src_files` mapea `"security/tutorial004_an_py310.py"` (relativo a `docs_src/`) → contenido. `fetch_docs` mantiene su firma; registra en stderr `resolved N includes, M missing`.
- Formato fijo: `ln[a:b,c,d:e]` = líneas 1-based inclusivas; entre rangos no contiguos se inserta la línea `# ...`. `hl[...]` (mismas reglas, números del archivo original) → cada línea resaltada termina en `  # highlight`. Sin `ln`, archivo completo. Ruta ausente → la línea `[code example: <ruta> not available]` (fuera de fence).
- **Variante:** el include ya nombra un archivo concreto (en 0.162.0 suele ser `_an_py310`); se usa **ese archivo** y no se agregan las variantes hermanas (`_py310`, `_py39`…). Justificar en decisión (D23): es la que la doc muestra por defecto, evita duplicar casi el mismo código en el índice y sesgar la búsqueda.

- [ ] **Step 1:** Tests (con `src_files` en memoria, sin tarball):
  - `test_full_file_include` → el placeholder desaparece, aparece ```` ```python ```` con el contenido.
  - `test_ln_ranges_with_gap` con archivo de 10 líneas `L1..L10` e include `ln[1:2,5,8:9]` → cuerpo exacto `L1\nL2\n# ...\nL5\n# ...\nL8\nL9`.
  - `test_hl_marks_lines` con `ln[1:3] hl[2]` → solo `L2  # highlight`.
  - `test_missing_file_is_reported` → texto contiene `[code example: x/missing.py not available]` y la ruta está en la lista devuelta.
  - `test_ln_out_of_range_is_clamped` (`ln[9:99]` en archivo de 10 líneas → `L9\nL10`, sin excepción).
  - `test_text_without_includes_unchanged`.
- [ ] **Step 2:** `uv run pytest tests/ingest/test_includes.py -v` → FAIL.
- [ ] **Step 3:** Implementar `resolve_includes` con una regex sobre `\{\*\s*(\S+)\s*(.*?)\s*\*\}` (ruta normalizada quitando el prefijo `../../docs_src/`). Extender `_docs_from_tarball` para recolectar `docs_src/**` (archivos bajo `<raíz>/docs_src/`).
- [ ] **Step 4:** Test `test_fetch_resolves_real_oauth2_page` (marcar `integration`? no: usa `data/fastapi-0.162.0.tar.gz` si existe, `pytest.skip` si no) → la página `tutorial/security/get-current-user.md` resuelta contiene `OAuth2PasswordBearer` y `get_current_user` y no contiene `{*`. Correr toda la carpeta `tests/ingest` → PASS.
- [ ] **Step 5:** Decisión D23. Commit `feat(ingest): resolver includes de docs_src respetando ln y hl`.

### Task 3: Troceado con tope real de 800 y bloques de código enteros

**Files:**
- Modify: `src/docs_agent/ingest/chunk.py`
- Test: `tests/ingest/test_chunk.py`

**Interfaces:**
- Consumes: texto ya resuelto (Task 2).
- Produces: `chunk_document(doc, max_tokens=800, overlap_tokens=100) -> list[Chunk]` (misma firma) con garantía: `count_tokens(c.content) <= max_tokens` para todo fragmento, **incluido el prefijo de solape**; ningún bloque de código ```` ``` ```` queda abierto en un fragmento y cerrado en otro, **salvo** un bloque que por sí solo exceda `max_tokens`: ese se parte por líneas en trozos que se cierran y reabren con la misma fence (```` ```python ````), y el trozo siguiente empieza con la línea `# (continued)`. El solape nunca se toma de dentro de un bloque de código (si la cola cae dentro de uno, sin solape).
- Produces también: `split_sections(doc) -> list[Section]` con `Section(url: str, title: str, content: str)` — una por intro/`##`/`###` con cuerpo, mismas URLs y títulos que usa `chunk_document` (reutilizar la lógica existente, sin duplicarla).

- [ ] **Step 1:** Tests:
  - `test_chunks_never_exceed_cap_including_overlap` (página sintética de muchos párrafos, `max=120, overlap=30`) → todos `<= 120`.
  - `test_code_block_not_split` (párrafos + bloque de 80 tokens que cae en el borde) → cada fragmento tiene un número par de líneas de fence.
  - `test_oversized_code_block_split_by_lines` (bloque de ~300 tokens, `max=120`) → varios fragmentos, cada uno con fences balanceadas, el 2.º empieza (tras la fence) con `# (continued)`, todos `<= 120`.
  - `test_sections_match_chunk_urls` → `{s.url for s in split_sections(doc)} == {c.url for c in chunk_document(doc)}`.
  - Los tests existentes de chunk siguen pasando.
- [ ] **Step 2:** `uv run pytest tests/ingest/test_chunk.py -v` → FAIL en los nuevos.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** `uv run pytest tests/ingest -v` → PASS. Script ad hoc (no se commitea) sobre el tarball: nº de fragmentos, mediana/máx de tokens, nº de bloques de código partidos; pegar los números en la decisión.
- [ ] **Step 5:** Decisión D24 "Troceado: tope con solape y bloques de código" (con los números). Commit `feat(ingest): tope real de 800 tokens sin partir bloques de código`.

### Task 4: Tabla `sections` + re-ingesta real

**Files:**
- Modify: `db/init.sql`, `src/docs_agent/ingest/store.py`, `src/docs_agent/ingest/run.py`
- Test: `tests/ingest/test_store.py`, `tests/ingest/test_run.py`

**Interfaces:**
- Produces: tabla `sections (id bigserial pk, source_ref text not null, url text not null, title text not null, content text not null, UNIQUE (source_ref, url))`; `replace_corpus(conn, source_ref, chunks, embeddings, sections: list[Section] = ()) -> int` reemplaza **chunks y sections** del `source_ref` en la misma transacción. `init.sql` sigue idempotente (`IF NOT EXISTS`); como solo corre en volumen nuevo (D14), la tabla se crea en la base existente aplicando `db/init.sql` con `docker compose exec -T db psql -U docs -d docs < db/init.sql`.

- [ ] **Step 1:** Tests de integración: `test_replace_corpus_replaces_sections` (dos llamadas; la 2.ª deja solo sus secciones) y `test_replace_corpus_rolls_back_sections_on_error` (embeddings de largo distinto → ni chunks ni sections cambian). `test_run_ingest_stores_sections` con `FakeOpenAI` y docs falsos.
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** `uv run pytest tests/ingest -v` PASS.
- [ ] **Step 5 (operación real, la ejecuta el controlador):** respaldo `docker compose exec -T db pg_dump -U docs docs > data/backup-docs-2026-11-10.sql` (verificar tamaño > 0); aplicar `init.sql` a `docs`; `uv run python -m docs_agent.ingest.run`. Si aborta por `INGEST_MAX_TOKENS`, **parar y reportar** (no subir el límite). Anotar: páginas, fragmentos, secciones, mediana/máx tokens, tokens de embedding, includes resueltos/faltantes.
- [ ] **Step 6:** Decisión D25 "Tabla `sections` para `get_section`" (por qué no reconstruir de fragmentos solapados) + actualizar D16 con una nota "ver D24/D25 (Semana 2)". Commit `feat(ingest): guardar secciones completas y re-ingestar con código`.

### Task 5: Calibrar el umbral "no sé" (D21)

**Files:**
- Create: `scripts/calibrate_threshold.py`, `scripts/calibration_questions.json`, `docs/calibracion-umbral.md`
- Modify: `src/docs_agent/config.py` (`no_answer_distance_threshold: float`), `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.no_answer_distance_threshold` (env `NO_ANSWER_DISTANCE_THRESHOLD`) con el valor elegido como default.
- `calibration_questions.json`: `{"in_corpus": [10 preguntas], "out_of_corpus": [10 preguntas]}`. Debe incluir **exactamente** la pregunta OAuth2 de la demo en `in_corpus` (`"¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el usuario actual? Muéstrame la sección exacta."`) y la de Django en `out_of_corpus` (`"¿Cómo configuro permisos en Django REST Framework?"`); mezcla ES/EN; las "fuera" incluyen otros frameworks y temas ajenos a la programación web.
- El script embebe las 20 preguntas (cuenta en presupuesto `ask`), usa `search` con `k=1` sobre `docs`, imprime tabla (pregunta, grupo, mejor distancia, URL) y escribe `docs/calibracion-umbral.md`.

- [ ] **Step 1:** Test `test_threshold_setting_from_env` (monkeypatch `NO_ANSWER_DISTANCE_THRESHOLD=0.5` → `0.5`).
- [ ] **Step 2:** FAIL → implementar el setting → PASS.
- [ ] **Step 3 (real, controlador):** `uv run python scripts/calibrate_threshold.py`.
- [ ] **Step 4:** Elegir el umbral: el punto medio entre el peor "dentro" y el mejor "fuera" si separan; **reportar explícitamente las distancias de OAuth2 y Django**. Si no separan: elegir el valor que preserva todas las "dentro" (prioridad: no decir "no sé" a una pregunta válida), anotar qué "fuera" quedan por debajo y que la defensa para esas es el clasificador del grafo + la regla "mencionar no es documentar" (decisión del dueño: **no** agregar señal léxica ni listas de páginas). Fijarlo como default.
- [ ] **Step 5:** D21 con la tabla, el valor, qué pasa si es muy alto (inventa con contexto pobre) o muy bajo (dice "no sé" a preguntas válidas). Commit `feat: umbral de no-sé calibrado con datos (D21)`.

### Task 6: Servidor MCP propio

**Files:**
- Create: `src/docs_agent/mcp_server/__init__.py`, `src/docs_agent/mcp_server/tools.py`, `src/docs_agent/mcp_server/server.py`, `src/docs_agent/mcp_server/__main__.py`, `src/docs_agent/tracing.py`
- Modify: `src/docs_agent/config.py`, `src/docs_agent/budget.py` (`KIND_MCP = "mcp"`), `src/docs_agent/rag/retrieve.py` (consultas de `list_sources`/`get_section`), `pyproject.toml` (deps `mcp>=2.3,<3`, `langsmith>=0.14,<0.15`; script `docs-agent-mcp = "docs_agent.mcp_server.__main__:main"`)
- Test: `tests/mcp_server/test_tools.py`, `tests/mcp_server/test_server.py`

**Interfaces:**
- Settings nuevos: `mcp_budget_scope: Literal["mcp","ask"] = "mcp"` (env `MCP_BUDGET_SCOPE`; valor inválido → `ValidationError` al arrancar → el proceso sale con código 1 y el mensaje `invalid MCP_BUDGET_SCOPE: <valor> (expected mcp|ask)` en stderr), `mcp_daily_token_budget: int = 100_000`, `langsmith_tracing: bool = False`, `langsmith_api_key: str = ""`, `langsmith_project: str = "docs-agent"`.
- `tracing.configure_tracing(settings) -> bool`: si `langsmith_tracing` y hay key, copia `LANGSMITH_TRACING/LANGSMITH_API_KEY/LANGSMITH_PROJECT` a `os.environ` y devuelve True; si no, False y nada más (sin warnings).
- `tools.py` (funciones puras sobre `conn` + cliente OpenAI, testeables sin MCP):
  - `list_sources(conn, settings) -> dict` → `{"project": "FastAPI", "version": settings.fastapi_docs_ref, "pages": int, "chunks": int, "sections": int}` (páginas = URLs sin ancla distintas).
  - `search_docs(conn, client, settings, query: str, k: int = 5) -> dict` → verifica presupuesto del `kind` = `settings.mcp_budget_scope` (límite `ask_daily_token_budget` si `ask`, `mcp_daily_token_budget` si `mcp`), embebe, busca, registra uso, devuelve `{"results": [{"title","url","distance","snippet"}], "best_distance": float|None, "in_corpus": bool, "notice": str|None, "embedding_tokens": int}`. `snippet` = primeros 300 caracteres. `in_corpus = best_distance <= no_answer_distance_threshold`. Si `in_corpus` es falso, `notice = "No relevant section in the indexed FastAPI docs. Do not answer from general knowledge."`. `k` acotado a 1..10. Presupuesto agotado → `BudgetExceeded`.
  - `get_section(conn, settings, url: str) -> dict` → `{"url","title","content"}`; URL sin ancla → intro + `"sections": [{"title","url"}]` de esa página; desconocida → `LookupError("Unknown section URL: <url>. Use search_docs to find valid URLs.")`. URL con espacios alrededor se recorta.
- `server.py`: `build_server(settings, conn_factory, client_factory) -> MCPServer` con `instructions` (texto fijo abajo) y las 3 herramientas decoradas con `@server.tool(description=...)` y `@traceable(name=<tool>, run_type="tool")`. Cada herramienta abre conexión vía `conn_factory`, devuelve el dict (salida estructurada) y escribe **una línea de log en stderr** con formato fijo:
  `[mcp] search_docs query="<q truncada a 60>" k=5 → 5 results · best=0.312 · in_corpus=yes · 143 ms`
  `[mcp] get_section url=<url> → 1 section · 2140 chars · 9 ms`
  `[mcp] list_sources → FastAPI 0.162.0 · 147 pages · 1234 chunks · 6 ms`
  Errores: `[mcp] get_section url=... → ERROR Unknown section URL · 4 ms` y la herramienta devuelve error MCP (no excepción cruda).
- `instructions` (texto fijo): `"Tools over the indexed FastAPI documentation (version {ref}). Answer ONLY with what these tools return and cite the exact URL. Use search_docs first, then get_section to read a full section. If search_docs returns in_corpus=false, say the indexed documentation does not cover it. Mentioning is not documenting: if results only mention a technology (for example another framework) without explaining how to use it, say the documentation does not cover it — at most, that it is mentioned — and never fill in from general knowledge."`
- `__main__.main()`: carga settings (sale con código 1 y mensaje si `MCP_BUDGET_SCOPE` es inválido), `configure_tracing`, `logging` a stderr, `build_server(...).run("stdio")`.

- [ ] **Step 1:** Tests unitarios/integración de `tools.py` (con `seeded_corpus` extendido con secciones y `FakeOpenAI`): `test_list_sources_counts`, `test_search_docs_shape_and_in_corpus_true`, `test_search_docs_out_of_corpus_sets_notice` (umbral bajo, p. ej. 0.0001), `test_search_docs_records_usage_under_scope` (parametrizado `mcp`/`ask` → `tokens_used_today(conn, scope) > 0` y el otro kind en 0), `test_search_docs_budget_exhausted_raises`, `test_get_section_unknown_url_error_mentions_search_docs`, `test_get_section_page_url_lists_sections`, `test_invalid_budget_scope_rejected` (`Settings(mcp_budget_scope="x")` → `ValidationError`) y `test_main_exits_1_on_invalid_scope` (subproceso `python -m docs_agent.mcp_server` con `MCP_BUDGET_SCOPE=x` → código 1, stderr contiene `invalid MCP_BUDGET_SCOPE`).
- [ ] **Step 2:** Test de servidor en proceso con `async with Client(build_server(...)) as c` (`@pytest.mark.anyio`, fixture `anyio_backend` = `"asyncio"` en conftest): `list_tools` devuelve exactamente `{"list_sources","search_docs","get_section"}` con descripción no vacía; `call_tool("search_docs", {"query": "request body"})` → `structured_content["results"]` no vacío; las `instructions` contienen `Mentioning is not documenting`; `capsys`/`caplog` muestra una línea que empieza con `[mcp] search_docs`.
- [ ] **Step 3:** Test pedido por el dueño, `test_get_section_oauth2_has_real_code` (integración; usa fetch real del tarball en caché + `split_sections` + guarda en `docs_test`; skip si no hay tarball): `get_section` de la sección de `tutorial/security/get-current-user/` que define `get_current_user` → contiene `OAuth2PasswordBearer` y `def get_current_user` (o `async def get_current_user`) y **no** contiene `{*`.
- [ ] **Step 4:** FAIL → implementar → `uv run pytest tests/mcp_server -v` PASS → suite completa PASS.
- [ ] **Step 5:** Decisiones: D26 "Servidor MCP propio vs MCP de n8n" (agente completo como 1 herramienta HTTP vs herramientas de bajo nivel sobre el corpus; conviven), D27 "Razonamiento en el cliente, no `ask_docs` en el servidor", D28 "Mencionado vs documentado" (caso Django con evidencia: 6 páginas, `alternatives.md` 16 menciones, DRF 6 veces; por qué se descartaron la lista de páginas y quitar `alternatives.md`), D29 "`MCP_BUDGET_SCOPE`". Commits separados: tools → server → decisiones.

### Task 7: Cliente MCP de sesión única con reconexión y timeout

**Files:**
- Create: `src/docs_agent/agent/__init__.py`, `src/docs_agent/agent/mcp_client.py`
- Modify: `src/docs_agent/config.py` (`mcp_call_timeout_s: float = 15.0`)
- Test: `tests/agent/test_mcp_client.py`

**Interfaces:**
- Produces: excepciones `DocsServerUnavailable(Exception)`, `DocsToolTimeout(DocsServerUnavailable)`, `DocsToolError(Exception)` (la herramienta devolvió `is_error`; el mensaje es el texto del error). Clase `DocsMCPClient(connect: Callable[[], AbstractAsyncContextManager[Client]], call_timeout_s: float)` con:
  - `async def call(self, tool: str, args: dict) -> dict` → abre la sesión perezosamente la 1.ª vez y la reutiliza; devuelve `structured_content`; `is_error` → `DocsToolError` (sin reconectar); error de transporte/proceso muerto → cierra la sesión, reconecta **una vez** y reintenta; si vuelve a fallar → `DocsServerUnavailable`; si la llamada excede `call_timeout_s` (usar `anyio.fail_after`) → `DocsToolTimeout` y se descarta la sesión (la siguiente llamada reconecta).
  - `async def aclose(self) -> None`.
  - Helper `stdio_connect(settings, scope: str) -> Callable[...]` que construye `StdioServerParameters(command=sys.executable, args=["-m", "docs_agent.mcp_server"], env={**os.environ, "MCP_BUDGET_SCOPE": scope}, cwd=<raíz del repo>)` y devuelve la fábrica `lambda: Client(params)`. Exponer `stdio_params(settings, scope) -> StdioServerParameters` para poder testearlo.
- Qué excepciones significan "proceso muerto" en mcp 2.3 sobre Windows: **determinarlo empíricamente** (matar el subproceso en un script ad hoc) y listarlas en el código con un comentario; como mínimo `anyio.ClosedResourceError`, `anyio.BrokenResourceError`, `anyio.EndOfStream` y `mcp.MCPError` con código de conexión cerrada.

- [ ] **Step 1:** Tests unitarios con una fábrica falsa (objetos que imitan `Client` como context manager async):
  - `test_session_is_reused` (2 llamadas → fábrica invocada 1 vez),
  - `test_reconnects_once_when_process_dies` (1.ª sesión lanza `anyio.ClosedResourceError` → fábrica invocada 2 veces, resultado de la 2.ª),
  - `test_gives_up_after_one_retry` (ambas fallan → `DocsServerUnavailable`),
  - `test_timeout_raises_and_next_call_reconnects` (sesión que duerme > `call_timeout_s=0.05` → `DocsToolTimeout`; la siguiente llamada usa una sesión nueva),
  - `test_tool_error_not_retried` (`is_error=True` → `DocsToolError`, fábrica 1 vez),
  - `test_stdio_params_pass_env_and_scope` (`params.env["MCP_BUDGET_SCOPE"] == "ask"` y contiene `DATABASE_URL` del entorno).
- [ ] **Step 2:** Test de integración `test_real_stdio_roundtrip` (servidor real por stdio contra `docs_test` con `seeded_corpus`; `OPENAI_API_KEY` falsa no sirve para `search_docs` → usar `list_sources` y `get_section`, que no llaman a OpenAI).
- [ ] **Step 3:** FAIL → implementar → PASS. Medir latencia de `list_sources` por stdio vs llamada directa a `tools.list_sources` (10 llamadas, mediana) y anotarla.
- [ ] **Step 4:** Decisión D30 "El grafo consume el servidor por MCP: sesión única, reconexión, timeout; costo frente a `retrieve.py`" (con la latencia medida). Commit `feat(agent): cliente MCP de sesión única con reconexión y timeout`.

### Task 8: Grafo LangGraph

**Files:**
- Create: `src/docs_agent/agent/graph.py`, `src/docs_agent/agent/classify.py`
- Modify: `pyproject.toml` (`langgraph>=1.2,<1.3`), `tests/fakes.py` (soporte de clasificación)
- Test: `tests/agent/test_graph.py`, `tests/agent/test_classify.py`

**Interfaces:**
- `classify.py`: `Classification(BaseModel)` con `is_fastapi: bool`, `reason: str`; `classify_question(client, question, model) -> tuple[Classification, int, int]` (prompt_tokens, completion_tokens) vía `client.chat.completions.parse(..., response_format=Classification, temperature=0)`. Prompt fijo: la pregunta cuenta como FastAPI si trata de FastAPI o de lo que su documentación cubre (Pydantic en FastAPI, Starlette, seguridad/OAuth2, despliegue, tipado de Python para APIs); cualquier otro framework o tema → `is_fastapi=false`.
- `FakeOpenAI(..., is_fastapi: bool = True)`: si `response_format` es `Classification`, devuelve `Classification(is_fastapi=self.is_fastapi, reason="fake")`; resto como hoy.
- `graph.py`:
  - `AgentState(TypedDict, total=False)`: `question`, `route`, `reason`, `results`, `best_distance`, `section`, `answer`, `citations`, `grounded`, `usage` (dict con `classifier_prompt_tokens`, `classifier_completion_tokens`, `embedding_tokens`, `prompt_tokens`, `completion_tokens`), `tools_used: list[str]`.
  - `AgentDeps` (dataclass): `openai` (cliente sync), `tools` (objeto con `async call(tool, args) -> dict`, p. ej. `DocsMCPClient`), `settings`, `check_budget: Callable[[], None]` (lanza `BudgetExceeded`).
  - `build_graph(deps: AgentDeps) -> CompiledStateGraph` con nodos `classify`, `search`, `evaluate`, `answer`, `no_se` y aristas: `START→classify`; `classify →(is_fastapi) search | no_se`; `search→evaluate`; `evaluate →(best_distance ≤ umbral) answer | no_se`; `answer→END`; `no_se→END`.
  - `classify`: `check_budget()` y luego clasificar; llamadas OpenAI sync envueltas en `asyncio.to_thread`. `search`: `tools.call("search_docs", {"query": q, "k": settings.top_k})`, añade `"search_docs"` a `tools_used`. `evaluate`: decide con `settings.no_answer_distance_threshold` (resultados vacíos → `no_se`, `insufficient_context`). `answer`: `check_budget()`, luego `tools.call("get_section", {"url": results[0]["url"]})` (añade `"get_section"`), construye contexto con la sección completa + los demás resultados y reutiliza `rag.answer.answer_question` (las citas se validan contra las URLs recuperadas, como hoy). `no_se`: `answer` fijo `"I couldn't find this in the indexed FastAPI documentation, so I won't guess."`, `citations=[]`, `grounded=False`, `route="no_se"`, `reason` = `out_of_domain` (desde clasificar) o `insufficient_context` (desde evaluar).
  - `mermaid(graph) -> str` = `graph.get_graph().draw_mermaid()`.
  - Nodos decorados con `traceable` es innecesario: LangGraph traza solo cuando `LANGSMITH_TRACING` está activo; el cliente OpenAI se envuelve con `wrap_openai` **solo** si `configure_tracing` devolvió True.
- `rag/answer.py`: `answer_question` acepta además el texto de la sección; ajustar `build_messages` sin cambiar el `SYSTEM_PROMPT` existente.

- [ ] **Step 1:** Tests con `FakeOpenAI` y un `FakeTools` (dict de respuestas por herramienta):
  - `test_normal_question_routes_to_answer` → `route=="answer"`, `grounded`, `tools_used == ["search_docs","get_section"]`, cita una URL de los resultados.
  - `test_out_of_domain_skips_search` (`is_fastapi=False`) → `route=="no_se"`, `reason=="out_of_domain"`, `FakeTools` sin llamadas, ninguna llamada de embeddings.
  - `test_insufficient_context` (best_distance > umbral) → `no_se`, `insufficient_context`, sin `get_section`.
  - `test_empty_results_insufficient_context`.
  - `test_budget_exhausted_raises_before_classifier` (`check_budget` lanza → `BudgetExceeded`, cero llamadas OpenAI).
  - `test_budget_exhausted_in_search_propagates` (`FakeTools` lanza `DocsToolError("daily token budget exceeded...")` → el grafo lo deja propagar).
  - `test_usage_includes_classifier_tokens_on_no_se`.
  - `test_mermaid_has_all_nodes` → contiene `classify`, `search`, `evaluate`, `answer`, `no_se`.
- [ ] **Step 2:** FAIL → implementar → `uv run pytest tests/agent -v` PASS.
- [ ] **Step 3:** Decisión D31 "Clasificador LLM vs reglas" y D32 "Por qué un grafo y no una sola llamada" (rutas explícitas, nodos testeables, traza por nodo). Commit `feat(agent): grafo clasificar → buscar → evaluar → responder | no_se`.

### Task 9: `/ask` sobre el grafo

**Files:**
- Modify: `src/docs_agent/api.py`, `tests/conftest.py`, `tests/test_api.py`, `docker-compose.yml` (si el servicio `api` necesita algo para lanzar el subproceso — normalmente nada)
- Test: `tests/test_api.py`, `tests/test_api_mcp_integration.py`

**Interfaces:**
- `api.py`: `lifespan` crea un `DocsMCPClient(stdio_connect(settings, "ask"), settings.mcp_call_timeout_s)` perezoso y lo cierra al apagar; dependencia `get_docs_tools()` (sobrescribible en tests). `/ask` pasa a `async def`, construye `AgentDeps` (con `check_budget` sobre `KIND_ASK`) y hace `await graph.ainvoke({"question": ...})`. Mapeo de errores: `BudgetExceeded` o `DocsToolError` cuyo mensaje contiene `budget` → 429 `"Daily token budget exhausted"`; `DocsServerUnavailable` → 503 `"Docs server unavailable"`; `openai.OpenAIError` → 502 `"Upstream model error"`. Se registra en `ask` solo lo que gastó la API (clasificador + respuesta); los embeddings los registra el servidor (scope `ask`). Corpus vacío → 503 como hoy (verificar con `corpus_size` antes del grafo).
- `AskResponse` añade `route: str` y `reason: str | None = None`; `usage` añade `classifier_tokens` (prompt+completion) sin quitar claves; `?debug=true` → `retrieved` = resultados de `search_docs` (`url`,`title`,`distance`).
- Tests de `/ask` existentes: fixture `client` sobrescribe además `get_docs_tools` con un `FakeTools` que llama a `tools.search_docs/get_section` en proceso contra `db_conn` (así siguen probando contra Postgres de tests). Sus aserciones no cambian.

- [ ] **Step 1:** Tests nuevos: `test_ask_returns_route_and_reason`, `test_ask_out_of_domain_no_se` (`is_fastapi=False` → 200, `route=="no_se"`, `reason=="out_of_domain"`, `grounded is False`, `citations == []`), `test_ask_docs_server_unavailable_503`, `test_ask_budget_exhausted_in_tool_429_no_usage`, `test_ask_usage_has_classifier_tokens`, `test_lifespan_builds_stdio_params_with_ask_scope` (Review Focus 3). Integración `test_graph_through_mcp_client` (requisito del spec: el grafo responde pasando por el cliente MCP): `DocsMCPClient(connect=lambda: Client(build_server(settings, conn_factory, lambda: FakeOpenAI())))` — protocolo MCP real, en proceso, contra `docs_test` — y `/ask` responde `route=="answer"` con cita. El subproceso stdio real no puede usar `FakeOpenAI`; el transporte stdio real queda cubierto en Task 7 (`list_sources`/`get_section`). Comentar esa elección en el test.
- [ ] **Step 2:** FAIL → implementar → suite completa PASS (52 originales + nuevos).
- [ ] **Step 3:** Verificar a mano que el workflow n8n sigue respondiendo: `integrations/n8n/smoke.sh 1` contra la api levantada con compose (si n8n no está levantado, documentarlo en el reporte y verificar al menos que el JSON de `/ask` conserva todas las claves que usa `integrations/n8n/workflows/*.json`).
- [ ] **Step 4:** Decisión D33 "Contrato extendido de `/ask` (`route`, `reason`)". Commit `feat(api): /ask usa el grafo por dentro`.

### Task 10: Tracing con LangSmith

**Files:**
- Modify: `src/docs_agent/api.py`, `src/docs_agent/agent/graph.py` (wrap opcional), `.env.example`, `README.md`
- Test: `tests/test_tracing.py`

**Interfaces:**
- Consumes: `tracing.configure_tracing` (Task 6). La API y el servidor MCP la llaman al arrancar; la API envuelve el cliente OpenAI con `wrap_openai` solo si devolvió True. Metadata de la corrida del grafo: `{"question": ..., "route": ...}` vía `config={"run_name": "ask", "metadata": {...}}` en `ainvoke` (verificar la clave exacta en la doc de LangGraph/LangChain instalada).
- `.env.example` añade `LANGSMITH_TRACING=false`, `LANGSMITH_API_KEY=`, `LANGSMITH_PROJECT=docs-agent`.

- [ ] **Step 1:** Tests: `test_tracing_disabled_by_default_leaves_env_untouched` (sin settings → `os.environ` sin `LANGSMITH_TRACING`), `test_tracing_enabled_sets_env` (monkeypatch), `test_ask_works_without_tracing` (ya cubierto por los tests de `/ask`; añadir aserción con `recwarn`: ningún warning emitido desde módulos `langsmith`).
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3 (controlador + dueño):** el dueño crea la cuenta LangSmith y pone `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY=...` en `.env` (los agentes no tocan `.env`). Luego una pregunta real a `/ask` y otra vía Claude Code → verificar en LangSmith la traza del grafo (nodos, tokens, latencia, costo) y las de herramientas.
- [ ] **Step 4:** Decisión D34 "LangSmith vs Langfuse". Commit `feat: tracing opcional con LangSmith`.

### Task 11: `scripts/demo_check.py`

**Files:**
- Create: `scripts/demo_check.py`, `src/docs_agent/pricing.py`
- Modify: `src/docs_agent/config.py` (precios), `pyproject.toml` (`rich>=15,<16`), `.env.example`
- Test: `tests/test_pricing.py`, `tests/test_demo_check.py`

**Interfaces:**
- Settings: `price_chat_input_per_mtok: float = 0.40`, `price_chat_output_per_mtok: float = 1.60`, `price_embedding_per_mtok: float = 0.02` (USD por millón; precios públicos de gpt-4.1-mini y text-embedding-3-small).
- `pricing.cost_usd(usage: dict, settings) -> float` sobre las claves de `usage` del grafo (clasificador + respuesta como chat; embeddings).
- `demo_check.py`: abre `DocsMCPClient(stdio_connect(settings, "ask"), ...)`; momento 1 → `list_sources` directo (ruta `"tool"`); momentos 2 y 3 → grafo. Esperado: 2 → `route=="answer"`, `"get_section" in tools_used`, alguna cita con `/tutorial/security/` en la URL; 3 → `route=="no_se"` y `reason=="out_of_domain"`. `--q "..."` corre solo esa pregunta por el grafo y muestra su fila (sin esperado → columna ✓/✗ vacía). `--skip-tests` evita correr pytest. Tabla rich con columnas **Pregunta, Ruta, Herramientas, Tokens, Costo USD, Latencia ms, ✓/✗**; debajo: **Costo total**, **Latencia promedio** y **"N tests passed"** (de `subprocess.run([sys.executable, "-m", "pytest", "-q"])`, parseando `(\d+) passed`). Debajo, el checklist manual del momento 3 en Claude: `"[ ] Claude no explica cómo configurar permisos de DRF; a lo sumo dice que la doc lo menciona como inspiración."`. Sale con código 1 si algún ✓/✗ es ✗. Respeta presupuesto (`BudgetExceeded` → mensaje claro y código 2).
- Separar la lógica testeable en funciones: `evaluate_expectation(moment: int, state: dict) -> bool`, `parse_passed(pytest_output: str) -> int | None`, `render(rows, summary) -> rich.table.Table`.

- [ ] **Step 1:** Tests: `test_cost_usd_known_values` (1 000 000 tokens de entrada de chat → 0.40; 1 000 000 de embedding → 0.02), `test_evaluate_expectation_moment2/3` (estados de ejemplo ✓ y ✗), `test_parse_passed("54 passed, 2 skipped in 3.1s") == 54`, `test_render_has_columns` (los 7 encabezados exactos).
- [ ] **Step 2:** FAIL → implementar → PASS.
- [ ] **Step 3 (real, controlador):** `uv run python scripts/demo_check.py` → los 3 automáticos ✓, tabla y resumen correctos; `uv run python scripts/demo_check.py --q "¿Cómo configuro permisos en Django REST Framework?" --skip-tests` → fila con `no_se`. Pegar la salida en el reporte.
- [ ] **Step 4:** Commit `feat(scripts): demo_check con tabla rich y modo --q`.

### Task 12: README, conexión desde Claude y cierre de decisiones

**Files:**
- Modify: `README.md` (inglés), `docs/decisiones.md`, `.env.example`, `docs/superpowers/specs/…` (solo si hubo erratas)
- Create: `scripts/export_mermaid.py` (imprime `mermaid(build_graph(...))` con deps falsas)

**Interfaces:** ninguna nueva.

- [ ] **Step 1:** README: sección "Agent graph" con el Mermaid **generado** por `scripts/export_mermaid.py` (no a mano); sección "MCP server" con las 3 herramientas, ejemplo de línea de log, y configuración exacta:
  - Claude Code: `claude mcp add docs-agent --scope local -- uv --directory C:/dev/docs-agent-langgraph-mcp run python -m docs_agent.mcp_server` (verificar la sintaxis con `claude mcp add --help`), `claude mcp list` → Connected.
  - Claude Desktop: bloque JSON `mcpServers.docs-agent` con `command: "uv"`, `args: ["--directory", "<repo>", "run", "python", "-m", "docs_agent.mcp_server"]`.
  - Cómo conviven el MCP de n8n y este (1 párrafo, enlaza D26). Sección "Tracing" (LangSmith opcional), "Demo rehearsal" (`demo_check.py`, `--q`), conteo de tests actualizado, nota de que los tests usan `docs_test`.
- [ ] **Step 2 (controlador):** conectar desde Claude Code con el comando del README y ensayar los momentos 1–3; verificar que los logs `[mcp] ...` se ven en stderr (log del servidor de Claude Code o lanzándolo en una terminal aparte).
- [ ] **Step 3:** Revisar que D21–D34 existan, numeradas y con formato **Elegido / Alternativas / Por qué**; índice al inicio de `decisiones.md` si existe.
- [ ] **Step 4:** `uv run pytest -q` → todo PASS. Commit `docs: README de la Semana 2 (grafo, MCP, tracing, demo)`.
