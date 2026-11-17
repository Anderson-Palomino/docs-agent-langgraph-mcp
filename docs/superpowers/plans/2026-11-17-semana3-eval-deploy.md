# Semana 3 — Evaluación, recalibración y despliegue · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Medir el grafo de `/ask` con un golden set de 30 casos (ruta, fuente, citas, fidelidad, latencia, costo), recalibrar el umbral de "no sé" con esos datos y dejar la API lista para desplegar con rate limit por IP.

**Architecture:** La lógica pura de la evaluación vive en un paquete nuevo `src/docs_agent/evaluation/` (golden set, métricas, juez, reporte); `scripts/evaluate.py` solo orquesta: corre cada caso con `make_deps` + `invoke_recording` como `/ask`, contra el servidor MCP real por stdio, gastando en un kind de presupuesto propio `eval`. La recalibración se calcula offline desde el JSON de la corrida. El rate limit es un módulo puro (`ratelimit.py`) enchufado como dependencia de `/ask`.

**Tech Stack:** Python 3.12, uv, FastAPI, LangGraph 1.2.20, MCP SDK 2.3.0, OpenAI SDK (`chat.completions.parse`), psycopg, rich, pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-semana3-eval-deploy-design.md` (leerlo entero antes de cualquier tarea).

## Global Constraints

- **Nunca leer, imprimir ni editar `.env`**; nunca imprimir un objeto `Settings` ni una excepción de `ValidationError` completa.
- Los tests nunca llaman a OpenAI ni a LangSmith (usar `tests/fakes.py: FakeOpenAI` y dobles de herramientas como `tests/agent/test_graph.py: FakeTools`).
- Los 206 tests existentes siguen pasando; `/ask` conserva contrato y códigos 422/429/502/503; el servidor MCP y `integrations/n8n/` no se rompen.
- Postgres en `127.0.0.1` (no `localhost`, D14); tests en la base `docs_test` (D22); la evaluación solo contra la base local `docs`.
- Ninguna API nueva sin verificarla en la documentación oficial (OpenAI SDK, proveedor de deploy, cabeceras del proxy). No inventar clases ni parámetros.
- Decisiones en `docs/decisiones.md`, español, formato `### DNN. Título` + `- **Elegido:**` / `- **Alternativas:**` / `- **Por qué:**` (opcional `- **Limitaciones:**` / `- **Revisar si:**`), desde D36.
- Commits pequeños; `git add <rutas explícitas>` (nunca `git add .`); trailer exacto `Co-Authored-By: Anderson Palomino <andersonpalominosandoval@gmail.com>`; **nunca** un trailer de Claude ni "Generated with Claude Code".
- Valores fijados por el spec: `eval_daily_token_budget=600_000`; `--max-tokens` default `400_000`; juez `gpt-4.1-mini`, `temperature=0`; umbrales a barrer `(0.48, 0.50, 0.52, 0.55)`; `ASK_RATE_LIMIT_PER_HOUR` default `20` (0 = desactivado); `TRUSTED_PROXY_IPS` default vacío, acepta `*`.
- Códigos de salida de scripts: 0 ok, 1 fallo, 2 presupuesto (como `scripts/demo_check.py`).
- Solo datos públicos (corpus FastAPI 0.162.0).

## Review Focus

1. Un caso cuya llamada al grafo falla (timeout MCP, error de OpenAI no-presupuesto) a mitad de la corrida: se registra `error` en ese caso, la corrida sigue, el caso queda fuera de las métricas pero se cuenta en `n_errors`, y el script sale con 1. (Tarea 5)
2. Golden set mal formado (id duplicado, `answer` sin URLs, `no_se` con URLs, distribución incompleta, `--only` con id desconocido): error claro y salida 1 **antes** de gastar un token. (Tareas 1 y 5)
3. `X-Forwarded-For` falsificado desde una IP no confiable, con varios valores, espacios o un valor que no es IP: se ignora o se cae a la IP del socket; nunca se cuenta a todos como una sola IP cuando `TRUSTED_PROXY_IPS=*`. (Tarea 7)
4. El juez devuelve rechazo o un `score` fuera de 0..1: el caso guarda `judge_error` y no tumba la corrida. (Tareas 4 y 5)
5. Ya existe `eval/results/<fecha>.json`: no se sobrescribe; se sufija `-2`, `-3`… (Tarea 5)

---

### Task 1: Golden set de 30 casos + tabla de revisión

**Files:**
- Create: `src/docs_agent/evaluation/__init__.py`, `src/docs_agent/evaluation/golden.py`
- Create: `eval/golden_set.json`, `scripts/golden_review.py`, `eval/golden_set_review.md` (generado)
- Test: `tests/evaluation/__init__.py`, `tests/evaluation/test_golden.py`

**Interfaces:**
- Produces: `GoldenCase` (pydantic: `id: str`, `question: str`, `lang: Literal["es","en"]`, `category: Literal[...8 categorías del spec 5.1]`, `expected_route: Literal["answer","no_se"]`, `expected_urls: list[str]`, `notes: str`, `judge_review: bool = False`); `load_golden(path: Path) -> list[GoldenCase]` (valida casos y unicidad de ids; lanza `GoldenSetError(ValueError)`); `check_distribution(cases) -> list[str]` (lista de problemas, vacía si cumple).

- [ ] **Step 1: Tests** en `tests/evaluation/test_golden.py`:
  - `test_load_rejects_duplicate_ids`, `test_answer_requires_urls`, `test_no_se_requires_empty_urls`, `test_judge_review_only_on_answer` → `pytest.raises(GoldenSetError)`.
  - `test_check_distribution_ok` con un set sintético que cumple; `test_check_distribution_reports_missing` (p. ej. 17 dentro → mensaje que menciona "in_corpus").
  - Reglas de `check_distribution`: 30 casos; 18 `in_*` con 9 `es` y 9 `en` y al menos 2 `in_multi`; 8 `out_*` con al menos 1 `out_obvious` y 1 `out_near`; 4 `trap_*` con al menos 1 de cada (`trap_mentioned`, `trap_ambiguous`, `trap_missing_fact`); exactamente 5 `judge_review`.
  - `test_real_golden_set_is_valid`: `load_golden(ROOT/"eval/golden_set.json")` y `check_distribution(...) == []`; además contiene las preguntas 2 y 3 de `scripts/demo_check.py: MOMENTS` (texto exacto) y **no** contiene la pregunta 1.
- [ ] **Step 2:** Correr `uv run pytest tests/evaluation/test_golden.py -v` → FAIL (módulo inexistente).
- [ ] **Step 3:** Implementar `golden.py`.
- [ ] **Step 4:** Redactar `eval/golden_set.json` siguiendo el spec 5.1. Las `expected_urls` salen de la tabla `sections` de la base local `docs` (solo lectura, `SELECT url, title FROM sections WHERE url ILIKE ...` vía `docs_agent.db.connect(get_settings().database_url)`), nunca escritas de memoria. Trampas: DRF/"mencionado" esperada `no_se`; ambigua y dato inexistente con la ruta que justifiques en `notes`. 5 `judge_review` repartidos (ES/EN, básica/intermedia/multi).
- [ ] **Step 5:** `scripts/golden_review.py`: carga y valida el set, comprueba cada `expected_url` contra `sections` (columna "¿existe?" ✓/✗) y escribe `eval/golden_set_review.md` con la tabla `| id | categoría | lang | pregunta | ruta esperada | URLs esperadas | ¿existe? | notas |`. No llama a OpenAI. Salida 1 si alguna URL no existe o la distribución falla.
- [ ] **Step 6:** `uv run python scripts/golden_review.py` → todas ✓, salida 0; `uv run pytest tests/evaluation -v` → PASS.
- [ ] **Step 7: Commit** `feat(eval): golden set de 30 casos y tabla de revisión`.

> **Pausa del controlador:** al terminar esta tarea, el controlador pasa `eval/golden_set_review.md` al dueño. Las tareas 2–5 no gastan tokens y siguen mientras el dueño valida; la tarea 6 no empieza sin la validación aplicada.

### Task 2: Kind de presupuesto `eval` (D39)

**Files:**
- Modify: `src/docs_agent/budget.py`, `src/docs_agent/config.py`, `src/docs_agent/mcp_server/tools.py` (`_budget_limit`), `src/docs_agent/mcp_server/__main__.py` (`_scope_error`), `src/docs_agent/agent/runner.py` (`make_deps`, `record_spent`), `.env.example`, `README.md` (tabla de config), `docs/decisiones.md`
- Test: `tests/test_budget.py`, `tests/test_config.py`, `tests/mcp_server/test_tools.py`, `tests/agent/test_runner.py`, test existente de `_scope_error`

**Interfaces:**
- Produces: `KIND_EVAL = "eval"`; `Settings.eval_daily_token_budget: int = 600_000`; `Settings.mcp_budget_scope: Literal["mcp","ask","eval"]`; `make_deps(conn, client, tools, settings, kind: str = KIND_ASK) -> AgentDeps` (chequea contra el límite del kind: `ask`→`ask_daily_token_budget`, `eval`→`eval_daily_token_budget`); `record_spent(conn, deps, kind: str = KIND_ASK) -> None`; helper `daily_limit(settings, kind: str) -> int` en `budget.py` o `config.py` (único lugar del mapeo kind→límite, usado por `make_deps` y `tools._budget_limit`).

- [ ] **Step 1: Tests:** `make_deps(..., kind="eval")` llama a `check_budget` con `"eval"` y 600 000 (monkeypatch); `record_spent(conn, deps, kind="eval")` registra en `eval` (integración `db_conn`); `tools.search_docs` con `mcp_budget_scope="eval"` registra en kind `eval`; `Settings(mcp_budget_scope="x")` falla y `_scope_error` devuelve `invalid MCP_BUDGET_SCOPE: x (expected mcp|ask|eval)`; los defaults de `/ask` siguen en `ask`.
- [ ] **Step 2:** Correr los tests → FAIL.
- [ ] **Step 3:** Implementar. `/ask` y `demo_check.py` no cambian de llamada (default `ask`).
- [ ] **Step 4:** `uv run pytest -q` → todo PASS.
- [ ] **Step 5:** D39 en `docs/decisiones.md`: kind `eval` + tope `--max-tokens` (400 000 por corrida, 600 000 diarios; la estimación del spec 5.2: ~280k tokens ≈ US$0.15); alternativas (mismo kind `ask`; solo documentar "correr en local"); por qué (no dejar sin cupo la demo en vivo). Agregar `EVAL_DAILY_TOKEN_BUDGET` a `.env.example` y a la tabla de config del README; `MCP_BUDGET_SCOPE` documenta `eval`.
- [ ] **Step 6: Commit** `feat(budget): kind eval con presupuesto propio (D39)`.

### Task 3: Métricas puras

**Files:**
- Create: `src/docs_agent/evaluation/metrics.py`
- Test: `tests/evaluation/test_metrics.py`

**Interfaces:**
- Consumes: forma de un caso resultado (dict), fijada aquí y usada por la Tarea 5: `id`, `category`, `expected_route`, `expected_urls`, `route` (`answer`|`no_se`|None si error), `reason` (`out_of_domain`|`insufficient_context`|None), `best_distance` (float|None), `retrieved_urls: list[str]`, `citations: list[str]` (URLs), `grounded: bool`, `latency_ms: float`, `cost_usd: float` (grafo + búsqueda extra), `judge: {"score","unsupported_claims","reason"} | None`, `judge_cost_usd: float`, `judge_error: str|None`, `error: str|None`.
- Produces:
  - `normalize_url(url: str) -> str`; `url_matches(cited: str, expected: str) -> bool`
  - `percentile(values: list[float], p: float) -> float | None` (interpolación lineal, como `numpy` por defecto; `None` si vacío)
  - `compute_metrics(cases: list[dict]) -> dict` con claves `n`, `n_errors`, `route_accuracy`, `confusion` (`answer_ok`, `false_no_se`, `false_answer`, `no_se_ok`), `source_hit_any`, `source_hit_all_multi`, `grounded_rate`, `faithfulness_mean` (float|None), `latency_p50_ms`, `latency_p95_ms`, `cost_total_usd`, `cost_per_question_usd`, `judge_cost_usd`. Cada tasa es `{"num": int, "den": int}`. Casos con `error` quedan fuera de todo salvo `n_errors`.
  - `simulate_route(case: dict, threshold: float) -> str` y `threshold_sweep(cases, thresholds=(0.48, 0.50, 0.52, 0.55)) -> list[dict]` con claves `threshold`, `cut_by_classifier`, `cut_by_threshold`, `false_no_se_classifier`, `false_no_se_threshold`, `false_answer`, `route_accuracy`.

- [ ] **Step 1: Tests** (`tests/evaluation/test_metrics.py`):
  - `normalize_url("http://FastAPI.tiangolo.com/tutorial/cors/") == "https://fastapi.tiangolo.com/tutorial/cors"`; el ancla se conserva: `normalize_url("https://x.com/a/#b") == "https://x.com/a#b"`.
  - `url_matches("https://x.com/a#b", "https://x.com/a") is True`; `url_matches("https://x.com/a#c", "https://x.com/a#b") is False`; `url_matches("http://X.com/a/#b", "https://x.com/a#b") is True`; `url_matches("https://x.com/ab", "https://x.com/a") is False`.
  - `percentile([100, 200, 300, 400], 50) == 250`; `percentile([100, 200, 300, 400], 95) == pytest.approx(385)`; `percentile([], 50) is None`.
  - `compute_metrics`: set de 4 casos (answer acertado con cita, falso no_se, falso answer, no_se ok) → `route_accuracy == {"num": 2, "den": 4}` y la confusión exacta; un `in_multi` con 2 esperadas y 1 citada → `source_hit_any` lo cuenta, `source_hit_all_multi == {"num": 0, "den": 1}`; un caso con `error` → `n_errors == 1` y fuera de los denominadores; `source_hit_any.den` solo cuenta esperada=obtenida=`answer`.
  - `threshold_sweep`: un caso `out_of_domain` cuenta en `cut_by_classifier` en todos los umbrales; un caso aceptado con `best_distance=0.51` es `answer` en 0.52 y 0.55 y `no_se` (cortado por umbral) en 0.48 y 0.50; si su esperada es `answer`, `false_no_se_threshold` sube en 0.48/0.50; un caso con `best_distance=None` y aceptado → `no_se` por umbral.
- [ ] **Step 2:** Correr → FAIL. **Step 3:** Implementar. **Step 4:** Correr → PASS.
- [ ] **Step 5: Commit** `feat(eval): métricas, coincidencia de URL y barrido de umbrales`.

### Task 4: LLM juez de fidelidad (D38, primera parte)

**Files:**
- Create: `src/docs_agent/evaluation/judge.py`
- Modify: `tests/fakes.py` (`FakeOpenAI` devuelve un `Judgment` cuando `response_format` es `Judgment`; configurable `judge_score`, `judge_refusal`)
- Modify: `docs/decisiones.md`
- Test: `tests/evaluation/test_judge.py`

**Interfaces:**
- Consumes: `docs_agent.agent.graph._cap_section` / `SECTION_MAX_CHARS` (mismo tope que vio el modelo; si se importa algo privado, promoverlo a público en `graph.py` sin cambiar su comportamiento).
- Produces: `JUDGE_MODEL = "gpt-4.1-mini"`; `JUDGE_PROMPT: str`; `Judgment(BaseModel)`: `score: float = Field(ge=0, le=1)`, `unsupported_claims: list[str]`, `reason: str`; `judge_context(state: dict) -> str` (fragmentos completos de `state["results"]` con su URL + texto de `state["section"]["content"]` con el tope, en el orden en que los vio el modelo; ver `rag/answer.py: build_messages`); `judge_answer(client, question: str, context: str, answer: str, model: str = JUDGE_MODEL) -> tuple[Judgment, int, int]` (`client.chat.completions.parse(..., response_format=Judgment, temperature=0)`, como `classify.py`); `JudgeError(Exception)` si el modelo rechaza (`parsed is None`).

- [ ] **Step 1: Tests:** `judge_answer` usa `JUDGE_MODEL` y `temperature == 0` y manda pregunta, contexto y respuesta en los mensajes; devuelve `(Judgment, prompt_tokens, completion_tokens)`; rechazo → `JudgeError`; `Judgment(score=1.2, ...)` → `ValidationError`; `judge_context` incluye la URL y el contenido de cada resultado y la sección truncada a `SECTION_MAX_CHARS` con la marca de truncado; sin sección (`None`) solo fragmentos.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. El prompt pide: juzgar solo si cada afirmación de la respuesta está apoyada en el contexto (no si es verdad en el mundo); una respuesta que dice honestamente que el contexto no cubre algo no se penaliza; listar las afirmaciones no apoyadas; `score` = fracción apoyada. **Step 4:** PASS.
- [ ] **Step 5:** D38 (borrador) en `docs/decisiones.md`: métricas de la evaluación (definiciones del spec 5.2, regla de URL con normalización, "al menos una" y "todas" para `in_multi`), el juez (modelo igual al que responde, temperature 0, prompt literal, salida estructurada), límites (mide apoyo en el contexto, no corrección; mismo modelo puede compartir sesgos con quien respondió; 30 casos es poco). Dejar una línea `- **Coincidencia con revisión manual:** pendiente (Tarea 6).`
- [ ] **Step 6: Commit** `feat(eval): LLM juez de fidelidad (D38)`.

### Task 5: `scripts/evaluate.py` + reporte

**Files:**
- Create: `src/docs_agent/evaluation/report.py`, `scripts/evaluate.py`
- Test: `tests/evaluation/test_report.py`, `tests/test_evaluate.py`

**Interfaces:**
- Consumes: Tareas 1–4 (`load_golden`, `check_distribution`, `compute_metrics`, `threshold_sweep`, `judge_context`, `judge_answer`, `JudgeError`); `make_deps(..., kind=KIND_EVAL)`, `record_spent(..., kind=KIND_EVAL)`, `invoke_recording`, `invoke_config`; `DocsMCPClient(stdio_connect(settings, "eval"), settings.mcp_call_timeout_s)`; `pricing.cost_usd`, `total_tokens`.
- Produces:
  - `report.py`: `results_path(directory: Path, day: date, suffix: str = ".json") -> Path` (no pisa: `<día>.json`, `<día>-2.json`…; el `.md` y el `-judge-review.md` comparten el mismo stem); `render_markdown(run: dict, metrics: dict, sweep: list[dict]) -> str` (tabla de métricas con porcentaje y `num/den`, latencias, costos; tabla de umbrales con las columnas de `threshold_sweep`); `render_judge_review(cases: list[dict], golden: list[GoldenCase]) -> str` (los 5 `judge_review`: id, pregunta, URLs del contexto, respuesta, puntaje y motivo del juez, columna vacía "puntaje del dueño").
  - `scripts/evaluate.py`: `async def run_cases(cases, settings, conn, client, tools, judge: bool, max_tokens: int, console) -> tuple[list[dict], str | None]` (resultados por caso + `aborted` = `None`|`"max_tokens"`|`"budget"`), inyectable en tests; `main(argv=None) -> int`.

Comportamiento de `run_cases` (por caso, en orden):
1. Si los tokens gastados en la corrida (grafo + búsqueda extra + juez, con `total_tokens`) ≥ `max_tokens` → parar, `aborted="max_tokens"`.
2. Grafo como `/ask` con `invoke_config(question, source="evaluate", case_id=id)`, cronometrando solo el `ainvoke` → `latency_ms`.
3. Si `state["reason"] == "out_of_domain"` (no buscó), llamar `tools.call("search_docs", {"query": q, "k": settings.top_k})` solo para `best_distance` y `retrieved_urls`; su `embedding_tokens` suma al costo del caso y al tope, no cambia la ruta.
4. Si la ruta es `answer` y `judge`: `judge_answer(client, q, judge_context(state), state["answer"])` en `asyncio.to_thread`, tras `check_budget(conn, KIND_EVAL, settings.eval_daily_token_budget)`; registrar sus tokens con `record_usage(conn, KIND_EVAL, ...)`; `JudgeError`/`ValidationError` → `judge_error`.
5. `BudgetExceeded` o `DocsToolError` de presupuesto → parar, `aborted="budget"`. Otros `DocsToolError`/`DocsServerUnavailable`/`openai.OpenAIError` → `error=<tipo>` en el caso y seguir.

`main`: flags `--golden` (default `eval/golden_set.json`), `--max-tokens` (default 400 000), `--only g01,g05`, `--no-judge`. Valida el set (`load_golden` + `check_distribution`, salvo con `--only`, que solo exige ids existentes) **antes** de abrir OpenAI/MCP → salida 1 con mensaje. Mismo arranque que `demo_check.py` (UTF-8 en stdout, `configure_tracing`, `make_openai(wrapper)`, arranque del servidor fuera del cronómetro con un `list_sources`, sesión abierta y cerrada en la misma tarea). Escribe `eval/results/<día Lima>.json` (`{"run": {...config: fecha, chat_model, judge_model, threshold, top_k, docs_ref, golden, max_tokens, aborted, tokens_total}, "cases": [...], "metrics": {...}, "sweep": [...]}`), el `.md` y el `-judge-review.md`; imprime una tabla `rich` con el resumen y el costo. Día Lima: `datetime.now(ZoneInfo("America/Lima")).date()` (si falta `tzdata` en Windows, agregarlo como dependencia). Salida: 2 si `aborted`, 1 si algún `error`, 0 si no. Errores de base de datos: solo el tipo, como `demo_check.py`.

- [ ] **Step 1: Tests de `report.py`:** `results_path` con `2026-11-18.json` existente devuelve `2026-11-18-2.json`; `render_markdown` contiene "Exactitud de ruta", "Acierto de fuente", "Citas válidas", "Fidelidad", "p50", "p95", "Costo" y una fila por umbral (`0.48` … `0.55`); `render_judge_review` lista solo los casos `judge_review`.
- [ ] **Step 2: Tests de `scripts/evaluate.py`** (cargar el script como en `tests/test_demo_check.py`; `FakeOpenAI` + un doble de herramientas tipo `FakeTools` que responde según la pregunta; `conn` de `db_conn`): golden set de 3 casos —`answer` (best 0.30), cortado por el clasificador (`is_fastapi=False` para esa pregunta), cortado por umbral (best 0.70)—:
  - `test_run_cases_three_cases`: rutas y `reason` esperados; el caso cortado por el clasificador tiene `best_distance` (la búsqueda extra se hizo) y su ruta sigue `no_se`; solo el caso `answer` tiene `judge`; los tokens quedaron en kind `eval` y nada en `ask`.
  - `test_run_cases_max_tokens_aborts`: `max_tokens=1` → tras el primer caso `aborted == "max_tokens"` y menos de 3 resultados.
  - `test_run_cases_tool_error_continues`: `search_docs` lanza `DocsServerUnavailable` en un caso → ese caso con `error`, los demás completos.
  - `test_run_cases_judge_refusal`: juez rechaza → `judge_error`, corrida sigue.
  - `test_main_rejects_invalid_golden` y `test_main_unknown_only_id` → `main([...]) == 1` sin construir cliente OpenAI (monkeypatch que falle si se llama).
- [ ] **Step 3:** FAIL. **Step 4:** Implementar (extraer a `runner.py` lo que `demo_check.py` y `evaluate.py` compartan, sin cambiar el comportamiento de `demo_check.py`). **Step 5:** `uv run pytest -q` → todo PASS.
- [ ] **Step 6:** Ignorar en git solo lo que no se publica: los resultados **sí** se commitean (`eval/results/` versionado).
- [ ] **Step 7: Commit** `feat(eval): scripts/evaluate.py con reporte Markdown y tope de tokens`.

### Task 6: Corrida real, revisión del juez y recalibración (D36, cierre de D38) — la hace el controlador

Requiere: golden set validado por el dueño y sus correcciones aplicadas (Tarea 1).

**Files:**
- Modify: `scripts/calibrate_threshold.py` (modo `--from-results PATH`), `docs/calibracion-umbral.md`, `docs/decisiones.md` (D36, D38, D21 "Pendiente")
- Create: `eval/results/<fecha>.json|.md|-judge-review.md`
- Test: `tests/test_calibrate_threshold.py`

- [ ] **Step 1:** `--from-results PATH` en `calibrate_threshold.py`: lee la corrida y escribe `docs/calibracion-umbral.md` con (a) la tabla de los casos ordenada por `best_distance` (`| id | Pregunta | Esperada | Clasificador | Mejor distancia | URL |`) y (b) la tabla `threshold_sweep` con columnas separadas clasificador / umbral. Sin OpenAI. Conserva el modo actual (20 preguntas) sin cambios. Test con un JSON de 3 casos en `tmp_path` (sin tocar el `docs/` real: la salida es parametrizable).
- [ ] **Step 2:** `uv run python scripts/evaluate.py` (real; cuesta ≈ US$0.15). Verificar la salida 0 y mostrar la tabla al dueño.
- [ ] **Step 3:** Pasar `eval/results/<fecha>-judge-review.md` al dueño para que puntúe los 5 casos. **Pausa.**
- [ ] **Step 4:** Con los puntajes del dueño: cerrar D38 (coincidencia, p. ej. "4 de 5 dentro de ±0.2", y qué casos discreparon y por qué).
- [ ] **Step 5:** `uv run python scripts/calibrate_threshold.py --from-results eval/results/<fecha>.json`; escribir D36 con la tabla de umbrales, el criterio asimétrico de D21 y la elección (si cambia, actualizar `Settings.no_answer_distance_threshold`, `.env.example`, README y tests que fijan 0.52; si no, justificar). D21: la línea "Pendiente" apunta a D36.
- [ ] **Step 6: Commit(s)** `eval: primera corrida del golden set`, `docs(decisiones): D36 umbral recalibrado`, `docs(decisiones): D38 coincidencia del juez`.

### Task 7: Rate limit por IP en `/ask`

**Files:**
- Create: `src/docs_agent/ratelimit.py`
- Modify: `src/docs_agent/config.py`, `src/docs_agent/api.py`, `tests/conftest.py` (aislar el limitador entre tests), `.env.example`, `README.md` (config)
- Test: `tests/test_ratelimit.py`, `tests/test_api.py`

**Interfaces:**
- Produces: `Settings.ask_rate_limit_per_hour: int = 20`, `Settings.trusted_proxy_ips: str = ""`; `parse_trusted(spec: str) -> TrustedProxies` (`""` → nadie, `"*"` → todos, lista separada por comas de IPs/CIDR con `ipaddress`; entrada inválida → `ValueError` al arrancar); `client_ip(peer: str | None, forwarded_for: str | None, trusted: TrustedProxies) -> str`; `SlidingWindowLimiter(limit: int, window_s: float, clock: Callable[[], float] = time.monotonic)` con `hit(key: str) -> float | None` (`None` si se permite; si no, segundos hasta liberar, para `Retry-After`) y sin crecer sin límite (purgar claves vacías).

- [ ] **Step 0:** Verificar en la documentación oficial de Render y Railway cómo llega `X-Forwarded-For` (¿el proxy agrega la IP del cliente al final o reemplaza la cabecera?, ¿el primer valor lo puede falsificar el cliente?). Si el primer valor es falsificable en un proveedor, usar el valor que ese proveedor garantiza (p. ej. el último agregado por su proxy) y dejarlo escrito en un comentario con el enlace a la doc y en D37 (Tarea 8). Anotar las URLs consultadas en el reporte.
- [ ] **Step 1: Tests** (`tests/test_ratelimit.py`): sin proxies confiables, `client_ip("10.0.0.1", "1.2.3.4", parse_trusted("")) == "10.0.0.1"`; con `"10.0.0.0/8"`, `client_ip("10.0.0.1", " 1.2.3.4 , 5.6.7.8", ...) == "1.2.3.4"` (o el valor que fije el Step 0); con `"*"` el peer siempre se trata como confiable; XFF con valor no-IP (`"unknown"`) → cae al peer; `parse_trusted("not-an-ip")` → `ValueError`. Limitador con reloj falso: 20 hits permitidos, el 21.º devuelve ≈3600 s; al avanzar el reloj 3600 s se permite otra vez; `limit=0` nunca bloquea.
- [ ] **Step 2: Tests de API** (`tests/test_api.py`): con `ask_rate_limit_per_hour=2`, la tercera llamada a `/ask` desde la misma IP → 429 con cabecera `Retry-After` (entero ≥ 1) y `detail` `"Rate limit exceeded"`, sin llamar al grafo ni a OpenAI; otra IP (vía XFF desde un proxy confiable) pasa; `/health` nunca se limita; con rate limit activo y `TRUSTED_PROXY_IPS` vacía, el arranque escribe el aviso `rate limit keyed by socket IP; set TRUSTED_PROXY_IPS behind a proxy` (caplog). El chequeo de rate limit va antes del chequeo de presupuesto y de la validación de la clave de OpenAI no se mueve.
- [ ] **Step 3:** FAIL. **Step 4:** Implementar (limitador en `app.state`, creado en el lifespan; un fixture autouse en `conftest.py` garantiza que ningún test existente choque con el límite). **Step 5:** `uv run pytest -q` → todo PASS (206 + nuevos).
- [ ] **Step 6:** `.env.example` y README: `ASK_RATE_LIMIT_PER_HOUR`, `TRUSTED_PROXY_IPS`.
- [ ] **Step 7: Commit** `feat(api): rate limit por IP en /ask con proxy confiable`.

### Task 8: Despliegue — D37 y guía (sin cuentas)

**Files:**
- Create: `docs/deploy.md`
- Modify: `docs/decisiones.md` (D37)

- [ ] **Step 1:** Investigar en la documentación oficial (WebFetch) y citar URLs: Render y Railway (plan gratuito o mínimo, costo mensual, cold start/sleep, RAM del plan para API + subproceso Python del servidor MCP, despliegue desde Dockerfile, cabecera `X-Forwarded-For`), Neon y Supabase (plan gratuito, `CREATE EXTENSION vector`, conexión directa vs pooled y compatibilidad con `psycopg`, límites de almacenamiento frente a ~1128 fragmentos × 1536 dims).
- [ ] **Step 2:** D37: tabla comparativa de las 2 + 2 opciones con costo mensual, plan gratuito, cold start y complejidad; recomendación con su porqué; protección de gasto (presupuesto diario existente, rate limit por IP por instancia que se reinicia con cada deploy, `TRUSTED_PROXY_IPS`, tope de gasto en el panel de OpenAI que configura el dueño); el servidor MCP sigue local (en el contenedor es un subproceso de la API).
- [ ] **Step 3:** `docs/deploy.md`: pasos para el proveedor recomendado — crear base, `db/init.sql` (extensión `vector`), ingesta única desde la máquina del dueño con `DATABASE_URL` de producción pasada por entorno solo para ese comando (nunca en archivos): `uv run python -m docs_agent.ingest.run` (verificar el comando real y `INGEST_MAX_TOKENS`), costo estimado (~180k tokens de embeddings); crear el servicio desde el Dockerfile; variables (nombre, de dónde sale el valor, sin valores): `OPENAI_API_KEY`, `DATABASE_URL`, `ASK_DAILY_TOKEN_BUDGET`, `ASK_RATE_LIMIT_PER_HOUR`, `TRUSTED_PROXY_IPS`, opcionales `LANGSMITH_*`; probar `/health` y `/docs`; tope de gasto en OpenAI (dónde se configura).
- [ ] **Step 4: Commit** `docs(deploy): D37 y guía de despliegue`.

> **Pausa del controlador:** entregar al dueño la lista exacta de cuentas, servicios, variables y comandos. Nada se crea ni se configura desde Claude. Cuando el dueño confirme el deploy, verificar `/health` y una pregunta a `/ask` contra la URL pública.

### Task 9: README, PLAN.md y D12

**Files:**
- Modify: `README.md`, `PLAN.md`, `docs/decisiones.md` (D12)

- [ ] **Step 1:** README, sección "Evaluación": tabla de la corrida (pegada de `eval/results/<fecha>.md`), cómo correr `scripts/evaluate.py` (flags, costo, kind `eval`, salidas), qué significa cada métrica y qué **no** mide; enlace a D36/D38; link de la demo en vivo si existe (si no, "deploy pendiente: ver D37").
- [ ] **Step 2:** `PLAN.md`: marcar `[x]` lo que esté hecho (S1, S2, S3 golden set; S3 trazas/deploy según corresponda).
- [ ] **Step 3:** D12: dejar escrito lo que se hace: autor noreply del repo; los commits de las Semanas 1–2 llevan `Co-Authored-By: Claude`; desde la Semana 3, por regla global del dueño, ningún trailer de Claude (trailer de coautoría del dueño); alternativas y por qué.
- [ ] **Step 4:** `uv run pytest -q` → todo PASS. **Commit** `docs: README con evaluación, PLAN.md y D12 al día`.
