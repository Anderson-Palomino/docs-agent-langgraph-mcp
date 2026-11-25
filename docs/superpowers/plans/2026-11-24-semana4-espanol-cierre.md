# Semana 4 — Español, cierre de pendientes y README — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que las preguntas válidas en español dejen de recibir "no sé" traduciendo la consulta de búsqueda dentro del clasificador, medirlo antes/después (golden set + holdout), cerrar los pendientes de D37/D38 y dejar README en inglés + guion del video.

**Architecture:** `Classification` gana `search_query`; el nodo `classify` decide la consulta efectiva (`state["search_query"]`, `state["translated"]`) y `search` la usa; `answer` sigue con la pregunta original. La evaluación registra esos campos; scripts nuevos comparan corridas, miden la búsqueda doble y arman la hoja del juez. El limitador expone qué entrada de `X-Forwarded-For` usó y la loguea enmascarada en el 429.

**Tech Stack:** Python 3.12, LangGraph, OpenAI (`gpt-4.1-mini`, `text-embedding-3-small`, Structured Outputs con `chat.completions.parse`), FastAPI, MCP SDK (stdio), Postgres + pgvector, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-11-24-semana4-espanol-cierre-design.md` (leerlo entero antes de cada tarea).

## Global Constraints

- Worktree `C:\dev\docs-agent-langgraph-mcp-semana4`, rama `feat/semana4-espanol-cierre`. Tests: `uv run pytest -q` (Postgres local en `127.0.0.1:5434`, tests de integración usan la base `docs_test`).
- **Nunca leer, imprimir ni editar `.env`** (ni `env.txt`); nunca imprimir un objeto `Settings`.
- Los tests nunca llaman a OpenAI ni a LangSmith: usar `tests/fakes.py::FakeOpenAI` y dobles de herramientas.
- Verificar en la doc oficial toda API nueva antes de usarla; no inventar parámetros.
- No romper `/ask` (contrato y códigos 422/429/502/503), el servidor MCP, n8n, el despliegue ni los 308 tests existentes.
- Decisiones en `docs/decisiones.md` desde D40, en español (Elegido / Alternativas / Por qué).
- Commits pequeños; `git status --short` antes de cada commit; `git add` con rutas explícitas; sin `git stash`. Trailer exacto, sin trailer de Claude:
  `Co-Authored-By: Anderson Palomino <andersonpalominosandoval@gmail.com>`
- Solo datos públicos; nada de BaldeCash, GENIA ni clientes.
- La evaluación corre contra la base local con kind `eval` (D39); nunca contra producción.
- Nada de push, PR, merge ni despliegue dentro de las tareas de código; eso lo hace el controlador con permiso del dueño.

## Review Focus

1. Traducción con solo espacios o con la pregunta original repetida en español → se busca con lo que diga la regla (espacios → original; texto no vacío → se usa tal cual). Test en Task 2.
2. `X-Forwarded-For` con una entrada no-IP en medio (`"1.2.3.4, basura, 5.6.7.8"`) → la resolución debe reportar la misma clave que `client_ip` hoy (la de la derecha si es IP) y el log no debe imprimir la entrada sin enmascarar. Test en Task 7.
3. Resultados viejos (`2026-11-17.json`) sin `search_query`/`translated`/`language` → `compare_runs` no falla y muestra "—". Test en Task 4.
4. Hoja del juez llenada a medias (filas sin sí/no) → `--score` cuenta solo las respondidas y reporta cuántas faltan, sin dividir por cero. Test en Task 5.
5. Holdout con distribución distinta a la del golden set → `evaluate.py --holdout` y `golden_review.py --holdout` no exigen la distribución de 30 casos, pero sí validan cada caso. Test en Task 1.

---

### Task 1: Holdout en español y soporte `--holdout`

**Files:**
- Create: `eval/holdout_es.json`, `eval/holdout_es_review.md` (generado)
- Modify: `scripts/evaluate.py` (`select_cases`, `main`, `write_outputs`), `src/docs_agent/evaluation/report.py:18` (`results_path`), `scripts/golden_review.py` (`main`)
- Test: `tests/test_evaluate.py`, `tests/evaluation/test_report.py`, `tests/evaluation/test_golden.py`

**Interfaces:**
- Produces: `results_path(directory: Path, day: date, suffix: str = ".json", label: str | None = None) -> Path` → `2026-11-24-holdout.json` con label, sin pisar (`-holdout-2`…). `select_cases(path, only, holdout: bool = False)`; CLI `evaluate.py --holdout` (sin chequeo de distribución, label `holdout`); `golden_review.py --holdout` (sin chequeo de distribución).

- [ ] **Step 1: Tests que fallan**
  - `test_results_path_with_label_does_not_overwrite`: con `tmp_path`, `results_path(tmp_path, date(2026,11,24), label="holdout")` → `2026-11-24-holdout.json`; tras crearlo, la siguiente → `2026-11-24-holdout-2.json`; sin label sigue `2026-11-24.json`.
  - `test_select_cases_holdout_skips_distribution`: un JSON de 2 casos válidos con `holdout=True` devuelve 2 casos; con `holdout=False` lanza `GoldenSetError` ("distribución").
  - `test_holdout_file_is_valid`: `load_golden(Path("eval/holdout_es.json"))` → 6 casos, ids `h01`–`h06`, todos `lang == "es"`, 4 `answer` y 2 `no_se`, al menos uno `category == "out_near"`, ningún `judge_review`, y ninguna pregunta idéntica a una del golden set.
- [ ] **Step 2:** `uv run pytest tests/test_evaluate.py tests/evaluation -q -k "label or holdout"` → FAIL.
- [ ] **Step 3: Implementar** `label` en `results_path` y `holdout` en `select_cases`/`main` (`--holdout` pasa `label="holdout"` a `write_outputs`). En `golden_review.py`, `--holdout` salta `check_distribution`.
- [ ] **Step 4: Escribir `eval/holdout_es.json`.** 4 `answer` en español (`in_basic`/`in_intermediate`), con `expected_urls` que existan en `sections` y, donde se pueda, páginas que no use el golden set (p. ej. CORS, archivos estáticos, `BackgroundTasks`, cabeceras de respuesta); preguntas redactadas como las haría un usuario, sin copiar títulos. 2 `no_se`: uno `out_obvious` (no técnico o de otro dominio) y uno `out_near` en español sobre Flask o Django (p. ej. "¿Cómo defino un blueprint en Flask para agrupar rutas?"). `notes` explica cada elección.
- [ ] **Step 5:** `uv run python scripts/golden_review.py --golden eval/holdout_es.json --out eval/holdout_es_review.md --holdout` → "6 casos, N/N URLs ✓". Tests en verde: `uv run pytest -q`.
- [ ] **Step 6: Commit** `eval/holdout_es.json eval/holdout_es_review.md scripts/evaluate.py scripts/golden_review.py src/docs_agent/evaluation/report.py tests/...` → `eval: holdout de 6 preguntas en español y --holdout`.
- [ ] **Step 7 (controlador): PAUSA 1.** Mostrar al dueño la tabla de `eval/holdout_es_review.md` y esperar su validación de rutas y URLs antes de cualquier corrida que gaste. Las Tasks 2–7 pueden avanzar mientras tanto.

### Task 2: Traducción dentro del clasificador (D40, opción A)

**Files:**
- Modify: `src/docs_agent/agent/classify.py`, `src/docs_agent/agent/graph.py` (`AgentState`, nodos `classify` y `search`), `tests/fakes.py` (`FakeOpenAI`)
- Test: `tests/agent/test_classify.py`, `tests/agent/test_graph.py`

**Interfaces:**
- Produces: `Classification.search_query: str | None`; `AgentState` gana `search_query: str` (consulta efectivamente usada) y `translated: bool`; `resolve_search_query(question: str, c: Classification) -> tuple[str, bool]` en `classify.py`. `FakeOpenAI(..., search_query: str | None = None)`.

- [ ] **Step 1: Verificar la doc oficial** de OpenAI Structured Outputs: cómo se declara un campo opcional/nullable (en modo estricto todos los campos son `required`; lo opcional se expresa como unión con `null`) y que `chat.completions.parse` con Pydantic `str | None` lo genera así. Anotar la URL para D40. Si la doc exige otra forma, usar esa.
- [ ] **Step 2: Tests que fallan** (LLM mockeado):
  - `test_classification_schema_has_search_query` (en el JSON schema, `search_query` admite `null`).
  - `test_prompt_asks_for_english_search_query_only_for_spanish`: el prompt menciona `search_query`, traducir al inglés, solo si `language` es `"es"`, `null` si es `"en"`, y no responder ni ampliar la pregunta.
  - `resolve_search_query`: `("¿Cómo…?", es, "How…?")` → `("How…?", True)`; `es` con `None`, `""` y `"   "` → `(pregunta, False)`; `en` con `"Otra cosa"` → `(pregunta, False)`; la traducción se usa con `strip()`.
  - `test_spanish_question_searches_with_translation_and_answers_with_original` (graph): `FakeOpenAI(language="es", search_query="How do I return status code 201?")`; el doble de herramientas registra que `search_docs` recibió `query == "How do I return status code 201?"`; el último mensaje de usuario de la llamada de respuesta contiene la pregunta original en español; `state["search_query"]` es la traducción y `state["translated"] is True`.
  - `test_english_question_searches_with_original`: `language="en"`, `search_query=None` → `search_docs` recibe la original; `translated is False`.
  - `test_english_with_translation_is_ignored`: `language="en"`, `search_query="algo"` → busca con la original.
  - `test_empty_translation_falls_back_to_original`: `language="es"`, `search_query="  "` → busca con la original; la ruta no cambia.
  - `test_out_of_domain_does_not_search_even_with_translation`: `is_fastapi=False, language="es", search_query="x"` → `search_docs` no se llama; `state["search_query"]` existe igual.
  - `test_refusal_has_no_translation`: `parsed=None` (rechazo) → `Classification(is_fastapi=False, language="en", search_query=None, …)`.
- [ ] **Step 3:** `uv run pytest tests/agent -q` → los nuevos FAIL.
- [ ] **Step 4: Implementar.** Campo y prompt (una viñeta nueva: traducción fiel al inglés, conservando identificadores de código como `Depends`, `status_code`, `Query`; sin responder ni ampliar; `null` si `language` es `"en"`). `resolve_search_query` con las reglas de la spec 5.1. `classify` devuelve `search_query` y `translated`; `search` usa `state["search_query"]`. `FakeOpenAI` pasa `search_query` al `Classification`.
- [ ] **Step 5:** `uv run pytest -q` → todo verde (308 + nuevos).
- [ ] **Step 6: Commit** → `feat(agent): traducción de la consulta en el clasificador (D40)`.

### Task 3: La evaluación registra la consulta usada

**Files:**
- Modify: `scripts/evaluate.py` (`_new_row`, `_fill_from_state`, búsqueda extra en `run_cases`)
- Test: `tests/test_evaluate.py`

**Interfaces:**
- Consumes: `state["language"]`, `state["search_query"]`, `state["translated"]` (Task 2).
- Produces: filas con `language: str | None`, `search_query: str | None`, `translated: bool | None`.

- [ ] **Step 1: Tests que fallan:** `test_row_records_language_search_query_and_translated` (fila con los tres valores del estado); `test_out_of_domain_extra_search_uses_search_query` (con `is_fastapi=False, language="es", search_query="Flask blueprint"`, la búsqueda extra recibe `"Flask blueprint"`); `test_out_of_domain_extra_search_english_uses_question`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar (la búsqueda extra usa `state.get("search_query") or case.question`). **Step 4:** `uv run pytest -q` verde.
- [ ] **Step 5: Commit** → `eval: registrar idioma y consulta de búsqueda por caso`.

### Task 4: Comparación antes/después

**Files:**
- Create: `src/docs_agent/evaluation/compare.py`, `scripts/compare_runs.py`
- Test: `tests/evaluation/test_compare.py`

**Interfaces:**
- Consumes: `compute_metrics`, `percentile` de `metrics.py`; JSON de `evaluate.py` (`{"run", "cases", "metrics", "sweep"}`).
- Produces:
  - `classifier_accuracy(cases: list[dict]) -> dict` (formato `_rate`): casos `answer` aciertan si `reason != "out_of_domain"`; casos `no_se` aciertan si `reason == "out_of_domain"`; `either` y casos con `error` fuera del denominador.
  - `classifier_flips(before: list[dict], after: list[dict]) -> list[dict]`: `{id, expected_route, before_cut: bool, after_cut: bool}` de los ids cuya decisión del clasificador cambió.
  - `es_out_of_corpus_rows(before, after) -> list[dict]`: casos `lang == "es"` con `expected_route in ("no_se", "either")`; `{id, route_before, route_after, cut_by_before, cut_by_after ("classifier"|"threshold"|None), distance_before, distance_after, closer: bool | None}`.
  - `case_detail(before, after, ids: list[str]) -> list[dict]`: `{id, question, distance_before, distance_after, route_before, route_after, search_query_after, retrieved_after}`.
  - `render_comparison(before_run: dict, after_run: dict, holdout_run: dict | None) -> str` (markdown).
  - CLI: `compare_runs.py BEFORE AFTER [--holdout PATH] [--out PATH]` (por defecto `eval/results/<día>-comparison.md`).

- [ ] **Step 1: Tests que fallan** con filas sintéticas mínimas:
  - `classifier_accuracy`: 2 `answer` (uno cortado), 1 `no_se` cortado, 1 `either` → 2/3.
  - `classifier_flips`: un caso cortado antes y no después aparece con `before_cut=True, after_cut=False`; los que no cambian no aparecen.
  - `es_out_of_corpus_rows`: `g25` con `reason="out_of_domain"` en ambos y distancias 0.4073 → 0.35 → `cut_by_after == "classifier"`, `closer is True`; un caso `en` no aparece.
  - `render_comparison`: contiene las filas "Ruta", "Ruta del clasificador", "Falsos «no sé»", "Falsos «respondí»", "Citas válidas", "Acierto de fuente", "Fidelidad", "Latencia p50", "Latencia p95", "Costo por pregunta (sin juez)", "Costo por pregunta (con juez)"; una sección "Español fuera del corpus" con `g25`; una sección de detalle con g03, g06, g07, g09; y con `holdout_run` una tabla "Holdout (prompt congelado, una corrida)" separada que no se suma a las anteriores.
  - Review Focus 3: filas sin `search_query`/`translated`/`language` → la celda muestra "—" sin excepción.
- [ ] **Step 2:** FAIL. **Step 3:** implementar (reutilizar `compute_metrics`; costo sin juez = `sum(cost_usd)/n` de casos sin error). **Step 4:** verde; `uv run python scripts/compare_runs.py eval/results/2026-11-17.json eval/results/2026-11-17.json --out <scratchpad>/x.md` corre sin error.
- [ ] **Step 5: Commit** → `eval: comparación de corridas antes/después`.

### Task 5: Hoja de revisión del juez (sí/no + nota) y puntaje

**Files:**
- Create: `scripts/judge_review_sheet.py`
- Modify: `src/docs_agent/evaluation/report.py` (`render_judge_review` y auxiliares), `scripts/evaluate.py` (`write_outputs` deja de escribir la hoja), docstring de `evaluate.py`
- Delete: `eval/results/2026-11-17-judge-review.md` (`git rm`)
- Test: `tests/evaluation/test_report.py`, `tests/test_evaluate.py`

**Interfaces:**
- Produces: `render_judge_review(cases: list[dict], golden: list[GoldenCase], extra_ids: list[str]) -> str`; `parse_review(markdown: str) -> list[dict]` con `{case_id, n, agree: bool | None}`; `score_review(rows) -> dict` con `{claims_answered, claims_total, claims_agree, case_agree, cases_answered, cases_total}`. CLI: `judge_review_sheet.py RESULTS.json --out PATH [--extra g03,g06,g07,g09]` y `judge_review_sheet.py --score PATH`.

- [ ] **Step 1: Tests que fallan:**
  - Hoja: para un caso respondido con 2 afirmaciones, hay una tabla `| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |` con 2 filas, columna Juez "apoyada"/"no apoyada" y celdas de acuerdo/nota vacías; la respuesta del modelo aparece; cada fragmento tiene extracto (~1500 caracteres) y su texto completo dentro de `<details>`.
  - Casos: los `judge_review` del golden set en orden, después los `extra_ids` **solo si** su `route == "answer"` (un extra con `no_se` no aparece); un marcado que no se respondió aparece con la nota "no se respondió en esta corrida" y sin tabla; si el total pasa de 10, `main` sale con código 1 y un mensaje para avisar al dueño, sin escribir el archivo.
  - `parse_review` + `score_review` (Review Focus 4): "sí"/"si"/"Sí"/"no" en cualquier caso; filas vacías cuentan en `claims_total` pero no en `claims_answered`; un caso está de acuerdo si todas sus afirmaciones respondidas son "sí" y no le falta ninguna; sin respuestas → sin división por cero.
  - `write_outputs` devuelve solo `[json, md]` y no crea `*-judge-review.md`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar; `git rm eval/results/2026-11-17-judge-review.md`. **Step 4:** `uv run pytest -q` verde.
- [ ] **Step 5: Commit** → `eval: hoja del juez con sí/no y cálculo de coincidencia`.

### Task 6: Medición de la búsqueda doble (opción C)

**Files:**
- Create: `scripts/measure_dual_query.py`
- Test: `tests/test_measure_dual_query.py`

**Interfaces:**
- Consumes: JSON de `evaluate.py` con `search_query`/`translated` (Task 3); el mismo cliente MCP que usa `evaluate.py` con `MCP_BUDGET_SCOPE=eval`.
- Produces: `measure(cases: list[dict], tools) -> list[dict]` (async) con `{id, expected_route, distance_original, distance_translated, top_url_original, top_url_translated, best_from: "original"|"translated"}` para casos `lang == "es"` con `translated` verdadero; `render_dual(rows) -> str` (tabla markdown). CLI: `measure_dual_query.py RESULTS.json --out PATH`.

- [ ] **Step 1: Tests que fallan** con un doble de `tools.call` que devuelve distancias fijas por consulta: dos llamadas por caso (original y traducida), `best_from` correcto, casos `en` o sin traducción omitidos, `render_dual` con una fila por caso.
- [ ] **Step 2:** FAIL. **Step 3:** implementar (arranque del cliente MCP igual que `evaluate.py._run`; registrar embeddings en `eval`). **Step 4:** verde.
- [ ] **Step 5: Commit** → `eval: medición de la búsqueda doble (opción C, D40)`.

### Task 7: Log del 429 con la clave enmascarada (D37)

**Files:**
- Modify: `src/docs_agent/ratelimit.py` (nueva resolución y máscara; `client_ip` queda como envoltura), `src/docs_agent/api.py:96-110` (`enforce_rate_limit`), `docs/deploy.md` (sección de verificación)
- Test: `tests/test_ratelimit.py`, `tests/test_api.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) ClientResolution(ip: str, source: Literal["peer", "xff"], xff_index_from_right: int | None, xff_entries: list[str])`; `resolve_client(peer, forwarded_for, trusted) -> ClientResolution` (misma lógica que `client_ip` hoy; `client_ip(...)` devuelve `resolve_client(...).ip`); `mask_ip(value: str) -> str` (IPv4 `a.b.x.x`; IPv6 o red /64 → primeros 32 bits + `:x:x::/64`; IPv4 mapeada → como IPv4; no-IP → `"<no-ip>"`; con puerto, se quita antes).

- [ ] **Step 1: Tests que fallan:**
  - `resolve_client` con `*` y `"9.9.9.9, 181.65.10.20"` → `ip="181.65.10.20"`, `source="xff"`, `xff_index_from_right=0`, 2 entradas; peer no confiable → `source="peer"`, índice `None`; Review Focus 2: `"1.2.3.4, basura, 5.6.7.8"` → mismo resultado que `client_ip` hoy.
  - Todos los tests actuales de `client_ip` siguen pasando sin cambios.
  - `mask_ip`: `"181.65.10.20"` → `"181.65.x.x"`; `"2800:200:abcd:1234::1"` y `"2800:200:abcd:1234::/64"` → `"2800:200:x:x::/64"`; `"::ffff:181.65.10.20"` → `"181.65.x.x"`; `"basura"` → `"<no-ip>"`; `"181.65.10.20:5555"` → `"181.65.x.x"`.
  - API (`caplog`, límite 1): la segunda petición con `X-Forwarded-For: 9.9.9.9, 181.65.10.20` → 429 y un WARNING de `docs_agent.api` con `key=181.65.x.x`, `source=xff`, `index_from_right=0`, `entries=2` y las entradas enmascaradas; el texto completo del log no contiene `181.65.10.20` ni `9.9.9.9`; la primera petición (200) no loguea nada de esto; el cuerpo y las cabeceras del 429 no cambian.
- [ ] **Step 2:** FAIL. **Step 3:** implementar; el warning se emite solo cuando `retry_after is not None`. Comprobar que un `logger.warning` de `docs_agent.api` sale a stderr con la configuración de uvicorn del contenedor (ya existe uno en `api.py:66`; si no saliera, usar el mismo mecanismo que ese).
- [ ] **Step 4:** `uv run pytest -q` verde.
- [ ] **Step 5: `docs/deploy.md`**, sección "Verificar la clave del límite por IP": el valor de `ASK_RATE_LIMIT` en producción (leer el nombre de la variable en `config.py`, no el valor del `.env`); un bucle de `curl` en PowerShell que haga `límite + 1` peticiones a `/ask` (cuerpo UTF-8 desde archivo con `--data-binary`); lo mismo con `-H "X-Forwarded-For: 1.2.3.4"`; repetir desde los datos móviles; en Render: servicio `docs-agent` → Logs → buscar `rate limit 429`; cómo leer `index_from_right`/`entries` y qué significaría cada resultado (entrada de la derecha = la agrega el proxy de Render y no se falsifica; si aparecen saltos propios de Render, la clave sería un salto).
- [ ] **Step 6: Commit** → `feat(ratelimit): log del 429 con la clave enmascarada (D37)`.

### Task 8 (controlador): Corridas reales, D40 y pausa 2

Requiere la Pausa 1 cerrada (holdout validado) y las Tasks 2–6 mergeadas en la rama.

- [ ] **Step 1:** Re-ingesta local no hace falta (mismo corpus). `uv run pytest -q` verde.
- [ ] **Step 2:** `uv run python scripts/evaluate.py` (golden set, con juez) → `eval/results/2026-11-24.{json,md}`.
- [ ] **Step 3:** `uv run python scripts/compare_runs.py eval/results/2026-11-17.json eval/results/2026-11-24.json`. Revisar el criterio de la spec 5.2bis: (1) `classifier_accuracy` no baja y no hay `answer` nuevo cortado; (2) sin falsos "respondí" nuevos, mirando aparte la sección "Español fuera del corpus"; (3) ≥ 3 de g03/g06/g07/g09 en `answer`.
- [ ] **Step 4:** Si no cumple: ajustar el prompt de traducción (máximo 2 veces en total), cada vez con commit propio y una línea en D40 (motivo y resultado), re-correr el golden set (salidas `-2`, `-3`). Tras el segundo ajuste sin cumplir: **parar**, documentar en D40 y marcar el español para la semana 5 (revertir la activación de la traducción antes del merge, según la spec 5.9).
- [ ] **Step 5:** Prompt congelado → `uv run python scripts/evaluate.py --golden eval/holdout_es.json --holdout` (una sola vez).
- [ ] **Step 6:** `uv run python scripts/measure_dual_query.py eval/results/<corrida final>.json --out eval/results/2026-11-24-dual-query.md`.
- [ ] **Step 7:** `uv run python scripts/calibrate_threshold.py --from-results eval/results/<corrida final>.json` → `docs/calibracion-umbral.md`; aplicar el criterio D21 (spec 5.5).
- [ ] **Step 8:** `compare_runs.py ... --holdout eval/results/2026-11-24-holdout.json` → `eval/results/2026-11-24-comparison.md`.
- [ ] **Step 9:** Escribir D40 (y D41 si cambia el umbral): opciones A–D con costo/latencia **medidos**, la URL de la doc de Structured Outputs, la ruta del clasificador antes/después, español fuera del corpus con g25, la tabla de C, el holdout aparte. Commit de resultados + D40.
- [ ] **Step 10: PAUSA 2.** Mostrar al dueño la comparación (las dos cifras por separado, la fila de español fuera del corpus y el detalle de g03/g06/g07/g09) y esperar su aprobación para desplegar.

### Task 9 (controlador): D39 en un commit aparte

- [ ] Corregir en D39 la estimación de ~280k tokens por corrida con lo medido (`run.tokens_total` de `2026-11-17.json` y de la corrida final). Commit aparte que solo toque esa línea → `docs(decisiones): D39 con los tokens medidos por corrida`.

### Task 10 (controlador): Hoja del juez y pausa 3

- [ ] **Step 1:** `uv run python scripts/judge_review_sheet.py eval/results/<corrida final>.json --out eval/results/2026-11-24-judge-review.md --extra g03,g06,g07,g09`. Si sale con "más de 10 casos", avisar al dueño antes de seguir.
- [ ] **Step 2:** Commit de la hoja vacía. **PAUSA 3:** pasar la ruta al dueño; no llenarla.
- [ ] **Step 3 (cuando la devuelva):** `judge_review_sheet.py --score eval/results/2026-11-24-judge-review.md`; D38 gana "Coincidencia con revisión manual (2026-11-24)" con los números y, si no coinciden, dónde falló el juez; el README reporta la fidelidad con ese respaldo. Si no llega antes del merge, D38 y README dicen "pendiente" y se completa en un PR corto.

### Task 11: README final, guion del video y PLAN.md

**Files:** Modify `README.md`, `PLAN.md`; Create `docs/demo-script.md`.

- [ ] Contenido según la spec 5.8: una frase de qué hace; Mermaid de la arquitectura; demo en vivo (URL, ejemplo en español e inglés, aviso de arranque en frío); local; tabla de evaluación con el holdout como medición limpia y el golden set aparte, aclarando que su prompt se ajustó mirando esos casos; limitaciones honestas; enlace a `docs/decisiones.md`. "Accepts questions in Spanish and English" solo si el español pasa el criterio y se despliega.
- [ ] `docs/demo-script.md`: 2 minutos por tramos (0:00–0:20 qué es; pregunta con citas; pregunta fuera del corpus → "no sé"; evaluación; MCP en Claude Code desde `demo/`, D35).
- [ ] `PLAN.md`: checklist de la S4.
- [ ] Verificar que cada cifra del README sale de un archivo de `eval/results/` (citar cuál en el commit). Commit → `docs: README final en inglés, guion del video y PLAN`.

### Task 12 (controlador): Revisión, PR, merge del dueño y verificación

- [ ] Revisión final de toda la rama (superpowers:requesting-code-review) y correcciones.
- [ ] `git log --oneline origin/main..HEAD`; push y PR con `GH_TOKEN=$(gh auth token --user Anderson-Palomino)`, cuerpo sin mención a Claude; solo con el permiso del dueño.
- [ ] El dueño confirma en Render que el servicio despliega `main` y **mergea él**.
- [ ] Verificación externa: `/health`; una pregunta en español y una en inglés con citas; una fuera del corpus con "no sé" (cuerpo UTF-8 con `--data-binary`). Resultado en D40/`docs/deploy.md`.
- [ ] El dueño corre la verificación del 429 (Task 7, Step 5) y pasa los logs; D37 gana su conclusión justificando la clave (qué entrada agrega el proxy, por qué no se falsifica, qué ajuste haría falta si no). Si no se hace esta semana, D37 documenta qué falta. Esto va en un PR corto posterior.
