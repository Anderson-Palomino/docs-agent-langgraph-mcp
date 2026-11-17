# Semana 3 — Evaluación con golden set, recalibración y despliegue (diseño)

Fecha: 2026-11-17 · Rama: `feat/semana3-eval-deploy` · Punto de partida: `C:\Users\ander\Downloads\SEMANA3_PLAN.md` (plan del dueño) + respuestas del brainstorming.

## 1. Intención

Poder contestar con números, en el README y en una entrevista, a *"¿cómo sabes que tu agente funciona?"*. Para eso: un golden set de 30 casos validado por el dueño, un script que mide el grafo por el mismo camino que `/ask`, el umbral de "no sé" recalibrado con esos datos (D36) y, si el tiempo alcanza, la API desplegada con un link público y protección de gasto (D37).

El dueño tiene poco tiempo esta semana. **Prioridad estricta:** golden set + evaluación → recalibración → despliegue. Si el despliegue no entra, la semana cierra con la evaluación y el deploy pasa a la Semana 4 (documentando qué falta).

## 2. Objetivos, no-objetivos, anti-objetivos

**Objetivos:** `eval/golden_set.json` (30 casos); `scripts/evaluate.py` con métricas de ruta, fuente, citas, fidelidad (LLM juez), latencia y costo; tabla de umbrales offline (D36); kind de presupuesto `eval`; rate limit por IP en `/ask`; guía de despliegue e ingesta en producción (D37); sección "Evaluación" del README; checklist de `PLAN.md`.

**No-objetivos:** registrar la corrida como experimento en LangSmith (queda como pendiente anotado); cambiar el Dockerfile; desplegar el servidor MCP (sigue local por stdio; dentro del contenedor la API lo lanza como subproceso); cambiar el grafo, el clasificador o el prompt de respuesta para que la evaluación salga mejor.

**Anti-objetivos (fallaría aunque "funcione"):**
- que la evaluación gaste contra el presupuesto diario de `/ask` y deje sin cupo la demo en vivo;
- que el juez sea un modelo más débil que el que responde;
- que la tabla de umbrales quede incompleta en los casos que el clasificador cortó antes de buscar;
- que el rate limit cuente a todos los usuarios como una sola IP (la del proxy) o que se pueda saltar falsificando `X-Forwarded-For`;
- que se lea, imprima o edite `.env`, o que Claude cree cuentas o maneje credenciales de producción;
- romper `/ask` (contrato y códigos 422/429/502/503), el servidor MCP, la integración n8n o los 206 tests existentes;
- APIs inventadas (proveedor de deploy, cabeceras del proxy, OpenAI): todo se verifica en la documentación oficial antes de usarlo.

## 3. Restricciones globales

- Flujo superpowers completo; commits pequeños; pytest en cada paso. Los tests nunca llaman a OpenAI ni a LangSmith.
- Decisiones nuevas en `docs/decisiones.md` desde D36, formato Elegido / Alternativas / Por qué, en español.
- Solo datos públicos (corpus FastAPI 0.162.0). Nada de BaldeCash, GENIA ni clientes.
- **Nunca leer, imprimir ni editar `.env`**; nunca imprimir un objeto `Settings`. Las variables de producción las configura el dueño en el panel del proveedor.
- Postgres local en `127.0.0.1:5434` (D14); la evaluación corre contra la base local `docs`, nunca contra producción. La base local ya tiene el corpus completo 0.162.0 (1128 fragmentos, 1070 secciones, D24); producción se ingiere desde el mismo tarball con el mismo código, así que las URLs y distancias valen para ambas.
- Firma de commits: autor con la config local del repo; trailer `Co-Authored-By: Anderson Palomino <andersonpalominosandoval@gmail.com>`; nunca un trailer de Claude (regla global del dueño). En este mismo PR se actualiza D12 para que diga lo que realmente se hace (desde la Semana 3, sin trailer de Claude; los commits anteriores lo llevan).

## 4. Orden de trabajo (decidido por el dueño)

1. Golden set propuesto → **pausa: el dueño valida la tabla de `expected_urls` (y rutas) antes de correr nada que gaste.**
2. `scripts/evaluate.py` (con kind `eval`) → corrida real → resultados.
3. Recalibración offline y D36.
4. Rate limit por IP + guía de deploy/ingesta → **pausa: lista exacta de cuentas y variables para el dueño.**
5. README + `PLAN.md`.

## 5. Diseño

### 5.1 Golden set (`eval/golden_set.json`)

Lista JSON de casos con: `id` (`g01`…`g30`), `question`, `lang` (`es`|`en`), `category` (`in_basic`|`in_intermediate`|`in_multi`|`out_obvious`|`out_near`|`trap_mentioned`|`trap_ambiguous`|`trap_missing_fact`), `expected_route` (`answer`|`no_se`|`either`), `expected_urls` (lista; vacía si `no_se`; con al menos una si `either`), `notes` (por qué está el caso), `judge_review` (bool; exactamente 6 casos en `true`, solo `answer` o `either`).

**`either` (decisión del dueño, caso g30 "FastAPI 1.0"):** las dos rutas son correctas. `no_se` es correcto; `answer` es correcto solo si alguna cita coincide con una `expected_url` (`deployment/versions`) y la respuesta no inventa fecha ni cambios (lo revisa el juez: g30 es el sexto caso `judge_review`). En la matriz de confusión, un `either` correcto cae en la celda "ok" de la ruta obtenida y uno incorrecto en falsos "respondí". En el barrido de umbrales un `either` nunca cuenta como error (bajo simulación no hay citas). g01 (momento 2 de la demo) espera solo `get-current-user`, para que la métrica sea exigente justo en la demo.

Distribución mínima (del plan): 18 dentro del corpus (9 ES / 9 EN; básicas, intermedias y algunas `in_multi` que necesitan 2 secciones); 8 fuera (obvias como cocina/deportes y cercanas: Django, Flask, Express, Pydantic fuera de FastAPI, Starlette puro); 4 trampa (mencionado ≠ documentado como DRF en `alternatives.md`, ambigua, dato que la doc no tiene como una versión futura). Incluye las preguntas 2 y 3 de la demo (`scripts/demo_check.py: MOMENTS`, OAuth2 y DRF). La pregunta 1 ("¿Qué documentación tienes disponible?") **no entra**: las preguntas sobre el corpus mismo las cubre `list_sources` en el cliente MCP y no forman parte de la evaluación del grafo; marcarla `no_se` premiaría que el grafo diga "no está en la documentación" sobre la documentación misma *(decisión del dueño)*. Su lugar lo ocupa otro caso dentro del corpus.

Las `expected_urls` se toman de URLs reales de la tabla `sections` de la base local (no se escriben a mano): el builder busca la sección candidata en la base y la propone. Se genera `eval/golden_set_review.md` con una tabla (id, pregunta, categoría, ruta esperada, URLs esperadas, notas) para que el dueño la valide. Mientras no esté validada, `evaluate.py` no se corre contra OpenAI. El dueño responde con comentarios sobre la tabla (no edita el JSON); Claude aplica las correcciones al JSON, regenera `golden_set_review.md` y, si hubo cambios de fondo, lo muestra otra vez *(decisión de Claude)*.

Una vez validado, el dueño revisa a mano el puntaje del juez en los 6 casos `judge_review` (ver 5.3).

### 5.2 `scripts/evaluate.py`

Corre cada caso por el mismo camino que `/ask`: `make_deps` + `build_graph(deps).ainvoke(...)` dentro de `invoke_recording`, con `invoke_config(question, source="evaluate", case_id=...)`, y el servidor MCP lanzado por `DocsMCPClient` (stdio). Reutiliza el cableado de `scripts/demo_check.py` donde aplique (sin duplicarlo: si hay que compartir, se extrae a `runner.py`).

**Presupuesto (kind propio `eval`):** `budget.py` gana `KIND_EVAL = "eval"`; `Settings` gana `eval_daily_token_budget` (default 600 000) y `mcp_budget_scope` acepta `eval`. `make_deps` recibe el kind (default `ask`, para no tocar `/ask`); `evaluate.py` usa `eval` en el grafo, en el juez y en el servidor MCP (scope `eval`), así nunca consume el cupo de `/ask`. Estimación que justifica los defaults *(decisión de Claude)*: un caso `answer` gasta ~6k tokens en el grafo (clasificador + contexto de 5 fragmentos y sección de hasta 12 000 caracteres) y otro tanto en el juez; ~22 casos `answer` × ~12k + el resto ≈ 280k tokens, ≈ US$0.15 con las tarifas de `pricing.py`. Además `--max-tokens` (default 400 000) es un tope por corrida: antes de cada caso se compara lo gastado en la corrida (grafo + búsquedas extra + juez) con el tope; si se superó, se para, se guardan los resultados parciales marcados `"aborted": "max_tokens"` y el script sale con código 2 (contrato de `demo_check`: 0 ok, 1 fallo, 2 presupuesto). `BudgetExceeded` del kind `eval` también sale con 2.

**`best_distance` en todos los casos:** si el clasificador rechazó la pregunta (no hubo búsqueda), el script llama aparte a `search_docs` (mismo cliente MCP, mismo `k=top_k`) después del grafo, solo para registrar `best_distance` y las URLs recuperadas. Esa llamada no altera la ruta registrada del grafo y su costo de embedding cuenta en la corrida.

**Por caso se guarda:** id, ruta esperada y obtenida, `reason` (`out_of_domain` = lo cortó el clasificador; `insufficient_context` = lo cortó el umbral), veredicto del clasificador (`is_fastapi`), `best_distance`, URLs recuperadas, citas, `grounded`, respuesta, usage, costo (`pricing.cost_usd`), latencia del grafo (solo el `ainvoke`, sin búsqueda extra ni juez), puntaje y motivo del juez.

**Métricas:**
- **Exactitud de ruta:** % de casos con ruta = esperada, y matriz de confusión 2×2 (falsos "no sé": esperada `answer`, obtenida `no_se`; falsos "respondí": esperada `no_se`, obtenida `answer`).
- **Acierto de fuente** (solo casos con esperada `answer` y obtenida `answer`; el denominador se reporta): "acertó al menos una" = alguna cita coincide con alguna `expected_url`. Para `in_multi` se reporta además "encontró todas las esperadas" = cada `expected_url` coincide con alguna cita.
- **Coincidencia de URL:** se normalizan ambas URLs (esquema `http`→`https`, host en minúsculas, sin barra final en el path, ancla conservada). Si la esperada tiene `#ancla`, la cita debe ser idéntica tras normalizar; si no tiene ancla, basta con que la cita sea de la misma página (mismo esquema+host+path, con cualquier ancla).
- **Citas válidas:** % de respuestas `answer` con `grounded=true`.
- **Fidelidad al contexto:** media del puntaje del juez en los casos `answer`.
- **Latencia:** p50 y p95 de la latencia del grafo (todos los casos).
- **Costo:** total de la corrida y por pregunta (media), separando grafo y juez.

**Salidas** (fecha local de la máquina que corre la evaluación, Lima; si ya existe el archivo del día se sufija `-2`, `-3`… *(decisión de Claude)*): `eval/results/<YYYY-MM-DD>.json` (casos + métricas + config: modelo, umbral, k, versión de la doc) y `eval/results/<YYYY-MM-DD>.md` con la tabla de métricas lista para pegar en el README y la tabla de umbrales (5.4). Por consola, una tabla `rich` con el resumen y el costo.

**Flags:** `--golden` (ruta, default `eval/golden_set.json`), `--max-tokens`, `--only <id,...>` (para repetir casos sueltos), `--no-judge`.

**Tests:** el script con un golden set de 3 casos (uno `answer`, uno cortado por el clasificador, uno cortado por el umbral) con el LLM y las herramientas falsos (patrón de `tests/fakes.py` y `tests/test_demo_check.py`); unitarios de normalización/coincidencia de URL, métricas (incluido `in_multi`), percentiles, tope `--max-tokens` y código de salida.

### 5.3 LLM juez (fidelidad)

Modelo `gpt-4.1-mini` (igual al que responde, nunca más débil), `temperature=0`, salida estructurada con `client.chat.completions.parse` (mismo patrón que `classify.py`): `{"score": float 0..1, "unsupported_claims": [str], "reason": str}`. Recibe la pregunta, el contexto exacto que vio el modelo que respondió (los fragmentos completos de `search_docs` y, si hubo, el texto de `get_section` con el mismo tope de `SECTION_MAX_CHARS`) y la respuesta. Pregunta solo si cada afirmación de la respuesta está apoyada en ese contexto (no si es correcta en el mundo real). Solo se aplica a casos con ruta obtenida `answer`. Sus tokens van al kind `eval` y al tope de la corrida; precio con las mismas tarifas de `pricing.py`.

**Revisión humana:** los 6 casos `judge_review: true` se listan en `eval/results/<fecha>-judge-review.md` (pregunta, contexto resumido con URLs, respuesta, puntaje y motivo del juez, columna vacía para el puntaje del dueño). El dueño los puntúa; la decisión del juez (D38) anota cuánto coincidió (p. ej. "5 de 6 dentro de ±0.2").

### 5.4 Recalibración offline (D36)

En el grafo actual (`agent/graph.py`) la ruta depende solo de dos cosas: el clasificador (`is_fastapi` falso → `no_se` con `reason=out_of_domain`, sin buscar) y el nodo `evaluate` (`answer` si hay resultados y `best_distance ≤ Settings.no_answer_distance_threshold`, hoy 0.52; si no, `no_se` con `insufficient_context`). No hay reranking ni otra condición, y un fallo de `get_section` no cambia la ruta (responde con los fragmentos). Por eso la simulación offline es exacta para la ruta.

Con la corrida guardada, para cada umbral en {0.48, 0.50, 0.52, 0.55} la ruta simulada es: `no_se` si el clasificador rechazó; si no, `answer` si `best_distance ≤ umbral`, si no `no_se`. Como `best_distance` existe en todos los casos (5.2), la tabla está completa. Por umbral se reportan falsos "no sé" y falsos "respondí", **separando qué decidió el clasificador y qué el umbral** (columnas: cortados por el clasificador, cortados por el umbral, falsos "no sé" por umbral, falsos "respondí"). Además, la tabla de distancias de los 30 casos ordenada (como la de D21) en `docs/calibracion-umbral.md`, reutilizando la lógica de `scripts/calibrate_threshold.py` o leyendo la corrida (sin otra llamada a OpenAI si los datos ya están).

Límite conocido: con un umbral distinto del real, un caso que pasa de `no_se` a `answer` no tiene respuesta generada; la tabla de umbrales mide ruta, no fidelidad.

Criterio de elección: el asimétrico de D21 (un falso "no sé" a una pregunta válida no lo corrige otra capa; una pregunta de fuera que pase el umbral todavía tiene el clasificador). Si 0.52 sigue siendo el mejor, se queda y se justifica con los datos nuevos.

### 5.5 Despliegue y protección de gasto (D37)

- **D37** compara 2 opciones de API (Render o Railway) + 2 de Postgres con pgvector (Neon o Supabase): costo mensual, plan gratuito, cold start y complejidad, verificado en la documentación oficial de cada proveedor, con una recomendación. Debe confirmar además que el plan elegido deja lanzar el subproceso del servidor MCP (RAM del plan gratuito: API + subproceso Python) y que la base admite `CREATE EXTENSION vector` y conexiones directas (no solo pooled en modo transacción, si `psycopg` lo necesita).
- **Rate limit por IP en `/ask`**, en memoria (sin dependencia nueva): ventana deslizante por IP, `ASK_RATE_LIMIT_PER_HOUR` (default 20; 0 = desactivado), responde 429 con `Retry-After`. La IP real: si la petición viene de un proxy confiable (`TRUSTED_PROXY_IPS`, lista de IPs/CIDR, vacía por defecto), se toma el primer valor de `X-Forwarded-For`; si no viene de un proxy confiable, se usa la IP del socket y se ignora la cabecera. El builder verifica en la documentación del proveedor elegido cómo llega `X-Forwarded-For` y qué IP tiene su proxy, y si el primer valor es fiable o lo puede falsificar el cliente; si no lo es, usa el valor que el proveedor garantiza y lo documenta. D37 deja escrito que el límite es por instancia y se reinicia con cada deploy. Si el proveedor no publica IPs fijas para su proxy, `TRUSTED_PROXY_IPS` acepta `*` (confiar en el salto inmediato, válido solo cuando la instancia no es accesible salvo a través del proxy), y la guía lo lista como variable obligatoria en producción. Al arrancar, si el rate limit está activo y `TRUSTED_PROXY_IPS` está vacía, la API escribe una línea de aviso en el log ("rate limit keyed by socket IP; set TRUSTED_PROXY_IPS behind a proxy") *(decisión de Claude)*. `/health` no tiene límite. La integración n8n (en local, red Docker) no debe quedar bloqueada con el default.
- **Presupuesto diario:** ya existe (`ASK_DAILY_TOKEN_BUDGET`). **Tope de gasto en OpenAI:** lo configura el dueño en el panel de OpenAI; la guía dice dónde.
- **Ingesta única en producción:** instrucciones (o un comando existente con `DATABASE_URL` de producción pasado por entorno, nunca escrito en archivos) para crear el esquema (`db/init.sql`, extensión `vector`) e ingerir la doc 0.162.0 una vez, con su costo estimado (~180k tokens de embeddings) y el tope `INGEST_MAX_TOKENS`.
- **`/health`** ya existe; la página para probar es el `/docs` de FastAPI.
- **Pausa obligatoria:** antes de cualquier paso que necesite una cuenta, Claude se detiene y entrega la lista exacta: qué cuenta crear, qué servicio, qué variables (nombre y de dónde sacar el valor, sin valores) y qué comando correr.

### 5.6 README y `PLAN.md`

Sección "Evaluación": tabla de resultados, cómo correr `scripts/evaluate.py`, qué significa cada métrica y qué no mide (p. ej. el juez mide apoyo en el contexto, no corrección; 30 casos es poco). Link de la demo en vivo si el deploy entra. Checklist de `PLAN.md` al día.

## 6. Decisiones nuevas previstas

- **D36** Umbral recalibrado con el golden set (tabla por umbral, clasificador vs umbral).
- **D37** Despliegue: proveedores comparados, protección de gasto, rate limit por IP (proxy confiable, por instancia).
- **D38** Evaluación: métricas, coincidencia de URL, LLM juez (prompt, modelo, límites, coincidencia con la revisión del dueño).
- **D39** Kind de presupuesto `eval` y tope `--max-tokens`.

## 7. Lo que queda al builder

Redacción exacta de las 30 preguntas (dentro de la distribución), el texto del prompt del juez, el formato visual de las tablas, cómo compartir código con `demo_check.py`, y el algoritmo de la ventana deslizante. El dueño valida el golden set y los 6 puntajes del juez; elige el proveedor final después de leer D37.
