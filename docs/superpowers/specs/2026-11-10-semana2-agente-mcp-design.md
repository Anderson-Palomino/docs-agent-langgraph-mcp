# Semana 2 — Agente LangGraph + servidor MCP propio (diseño)

Fecha: 2026-11-10 · Rama: `feat/semana2-agente-mcp` · Punto de partida: `C:\Users\ander\Downloads\SEMANA2_PLAN.md` (plan del dueño) + respuestas del brainstorming.

## 1. Intención

Convertir `/ask` en un agente LangGraph y construir un servidor MCP propio sobre el corpus de FastAPI, **pensado para una demo grabada de 2 minutos** (pantalla dividida: Claude a la izquierda; logs del servidor MCP o traza de LangSmith a la derecha). Todo se mide contra esa demo. El código se estudia luego para entrevistas, así que cada decisión importante va a `docs/decisiones.md` (D21, D22…, formato Elegido / Alternativas / Por qué, en español).

### Los 4 momentos de la demo (no pueden fallar)
1. *"¿Qué documentación tienes disponible?"* → Claude llama `list_sources`.
2. *"¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el usuario actual? Muéstrame la sección exacta."* → `search_docs`, luego `get_section`, respuesta con la URL citada **y el código real** de la sección. A la derecha, la traza en LangSmith de las herramientas (con distancias y ms).
3. *"¿Cómo configuro permisos en Django REST Framework?"* → en Claude: `search_docs` puede devolver `in_corpus: true` si encuentra la sección de DRF en `alternatives.md` (es verdad: DRF está **mencionado**); Claude no debe explicar cómo configurar permisos de DRF — a lo sumo dice que la doc lo menciona como inspiración, porque **mencionado no es documentado**. Además, la misma pregunta va al grafo (`/ask` o `demo_check.py --q "..."`) y a la derecha se ve en LangSmith la traza del grafo tomando la ruta "no sé" con su `reason`.
4. Pantalla de cierre: salida final de `demo_check.py` en terminal (ver §7).

## 2. Objetivos, no-objetivos, anti-objetivos

**Objetivos:** resolución de includes `docs_src` + re-ingesta; grafo LangGraph detrás de `/ask`; servidor MCP stdio con 3 herramientas y logs legibles; el grafo consume ese servidor como cliente MCP; tracing LangSmith opcional; base de tests separada; `scripts/demo_check.py`; diagrama Mermaid en README; decisiones nuevas.

**No-objetivos (Semana 3+):** golden set de 30, script de evaluación, despliegue, varios corpus, una 4.ª herramienta `ask_docs` (descartada, ver §5.4).

**Anti-objetivos (fallaría aunque "funcione"):** que el momento 2 muestre placeholders `{* ... *}` en vez de código; que Claude o el grafo respondan Django desde conocimiento propio; que se rompa `/ask` o la integración n8n (`integrations/n8n/`); que correr los tests borre la base de la demo; caminos nuevos que gasten tokens sin pasar por `budget.py`; APIs de LangGraph / MCP inventadas.

## 3. Restricciones globales

- Flujo superpowers completo; commits pequeños; pytest en cada paso.
- **Antes de usar una API de LangGraph, del SDK oficial de MCP (`mcp`) o de LangSmith, verificar en la documentación oficial el nombre y la firma en la versión instalada.** Fijar versiones en `pyproject.toml` / `uv.lock`.
- Solo datos públicos; nada de datos de empleadores ni clientes.
- Presupuesto de tokens (`budget.py`) en todos los caminos que gastan (clasificador, embeddings de `search_docs`, respuesta). Los tests nunca llaman a OpenAI ni a LangSmith.
- Postgres en `127.0.0.1:5434`; usar `127.0.0.1`, no `localhost` (D14).
- Hoy hay **52 tests** (23 unitarios + 29 de integración); todos siguen pasando.
- `/ask` conserva su contrato (campos `answer`, `citations`, `grounded`, `usage`, `retrieved?`; códigos 422/429/502/503) y solo **añade** campos.
- Identidad git y trailer como en D12.

## 4. Orden de trabajo (decidido por el dueño)

1. **Base de tests separada** (para que todo lo siguiente se pruebe sin tocar la base de la demo).
2. **Resolución de includes `docs_src` + troceado** → re-ingesta.
3. **Calibración del umbral (D21)** — solo después de la re-ingesta, porque cambia las distancias.
4. Servidor MCP → cliente MCP → grafo → `/ask` → tracing → `demo_check.py` → README.

## 5. Diseño por partes

### 5.1 Base de tests separada (mi decisión, aprobada)
- Nueva base `docs_test` en el mismo contenedor Postgres; `TEST_DATABASE_URL` (default `postgresql://docs:docs@127.0.0.1:5434/docs_test`).
- El conftest la crea si no existe (conectando a la base de mantenimiento) y aplica `db/init.sql` (idempotente). El fixture `db_conn` y cualquier test de integración usan **solo** `TEST_DATABASE_URL`; nunca truncan `docs`.
- Hecho cuando: correr la suite completa deja intactos los fragmentos de la base `docs`.

### 5.2 Includes `docs_src` y troceado
- En el tag 0.162.0 las páginas usan `{* ../../docs_src/<ruta>.py <opciones> *}`; los archivos viven en `docs_src/` del mismo tarball (fuera de `docs/en/docs/`). `fetch` debe leerlos del tarball también.
- Reemplazar cada include por un bloque ```` ```python ```` con el código real.
- **Respetar `ln[...]`** (rangos de líneas a incluir) y **`hl[...]`** (líneas resaltadas): las resaltadas se conservan de forma visible (p. ej. comentario `# ← resaltado` o metadato) — el builder elige la forma y la justifica; no se descartan.
- **Variantes** (`_py39`, `_py310`, `_an`, `_an_py310`…): elegir **una sola** por include, con regla determinista; candidata: la más moderna existente (preferir `_an_py310`, luego `_an_py39`, `_an`, `_py310`, …). Confirmar la regla con los archivos reales del tag y justificarla en una decisión.
- Include que no se puede resolver (archivo ausente): dejar una línea legible (`[code example: <ruta> not available]`) y contarlo en el log de ingesta; nunca romper la ingesta.
- **Troceado:** ningún fragmento pasa de `CHUNK_MAX_TOKENS` (800) **contando el prefijo de solape** (hoy el tope real es ~900; máx observado 1130). Un bloque de código nunca se parte entre fragmentos; si un bloque de código solo excede el tope, medir cuántos hay y decidir con datos (p. ej. partir por líneas cerrando y reabriendo la fence) — anotarlo en una decisión.
- Guardar además el **texto completo de cada sección** (tabla `sections`: `source_ref`, `url` con ancla, `title`, `content`) para que `get_section` devuelva la sección entera sin reconstruirla de fragmentos solapados.
- Re-ingesta con el límite `INGEST_MAX_TOKENS` vigente; anotar nuevas estadísticas (páginas, fragmentos, mediana/máx de tokens, tokens de embedding).
- **Test pedido por el dueño:** con la página de OAuth2 (`tutorial/security/get-current-user/` o la que corresponda a "usuario actual"), `get_section` devuelve código real (`OAuth2PasswordBearer`, `get_current_user`) y no contiene `{*`.

### 5.3 Umbral "no sé" (D21)
- `NO_ANSWER_DISTANCE_THRESHOLD` (env). Elegido con datos tras la re-ingesta: 10 preguntas dentro del corpus y 10 fuera (incluida la de Django de la demo), registrar la distancia del mejor fragmento de cada una, elegir el valor y anotar en D21 la tabla, el valor y qué pasa si es muy alto o muy bajo. Guardar el script/datos de calibración en el repo.
- El mismo umbral lo usan el nodo "evaluar contexto" del grafo y `search_docs` (`in_corpus`).
- **Decisión del dueño (caso Django):** el corpus sí contiene "Django" (6 páginas; `alternatives.md` 16 veces) y "Django REST Framework" (6 veces en `alternatives.md`). Primero se mide la distancia de la pregunta de Django vs la de OAuth2 y se anotan los números en D21. **No** se agrega señal léxica, **ni** lista de páginas "que solo mencionan" (regla a la medida de la demo, no escala), **ni** se quita `alternatives.md` (quitar datos para que pase). Las defensas son: el clasificador del grafo y la línea "mencionar no es documentar" en las `instructions`. La pregunta de Django de la demo no se cambia. Todo esto va a una decisión (mencionado vs documentado, con el caso Django como evidencia, y por qué se descartaron la lista y quitar páginas).

### 5.4 Servidor MCP (SDK oficial `mcp`, transporte stdio)
Herramientas, con descripciones claras para que el modelo sepa cuándo usar cada una:
- `list_sources()` → proyecto (FastAPI), versión (`FASTAPI_DOCS_REF`), número de páginas (URLs sin ancla distintas) y de fragmentos.
- `search_docs(query, k=5)` → lista de `{title, url, distance, snippet}` + `in_corpus: bool` (mejor distancia ≤ umbral) + aviso explícito cuando `in_corpus` es falso (p. ej. "No relevant section in the indexed FastAPI docs; do not answer from general knowledge."). Gasta embeddings → presupuesto (rechaza con error claro si se agotó; registra uso).
- `get_section(url)` → texto completo de la sección (de `sections`); URL desconocida → error claro con sugerencia de usar `search_docs`.
- **`instructions` del servidor:** responder solo con lo que devuelvan estas herramientas, citar la URL, y si `in_corpus` es falso decir que no está en la documentación indexada. Además: **mencionar no es documentar** — si los resultados solo mencionan una tecnología (p. ej. otro framework) sin explicar cómo usarla, decir que la documentación no la cubre y, como mucho, que se menciona; nunca completar con conocimiento general.
- **Logs legibles** (stderr, porque stdout es el canal MCP): una línea por llamada con herramienta, argumentos, nº de resultados, mejor distancia y ms. Debe entenderse de un vistazo en la demo.
- Las 3 herramientas se **trazan en LangSmith** cuando el tracing está configurado.
- Convive con el MCP de n8n (`02-mcp-docs-agent`): aquel expone el agente completo como una herramienta HTTP; este expone herramientas de bajo nivel sobre el corpus. Va a una decisión (pedido del dueño).
- **Descartado: 4.ª herramienta `ask_docs`** que ejecute el grafo — duplicaría el MCP de n8n y haría al servidor cliente de sí mismo. Decisión (pedido del dueño): el razonamiento queda en el cliente (Claude o el grafo) y el servidor solo expone datos; explicar por qué.
- Configuración exacta para Claude Code (`claude mcp add ...`) y Claude Desktop documentada en README.
- Tests de las 3 herramientas.

### 5.5 Cliente MCP del grafo
- El nodo "buscar" no llama directo a la base: usa `search_docs` (y `get_section` cuando necesite más contexto — criterio a definir por el builder y anotarlo) a través de un cliente MCP.
- **Una sola sesión stdio** abierta al arrancar la API (lifespan) y reutilizada (mi decisión, aprobada). **Requisito del dueño:** si el proceso del servidor muere, el cliente lo relanza y reintenta la llamada una vez; **timeout por llamada** configurable (`MCP_CALL_TIMEOUT_S`). Tests de la reconexión y del timeout.
- Decisión: ventajas (un solo servidor para el agente y Claude, contrato único) vs costo (latencia extra, un proceso más) frente a llamar `retrieve.py`; medir la latencia extra y anotarla.
- Test de integración: el grafo responde una pregunta pasando por el cliente MCP real (servidor stdio real, base de tests, OpenAI falso).

### 5.6 Grafo LangGraph
Nodos: **clasificar → buscar → evaluar contexto → responder**, más **no sé**.
- **clasificar** (mi decisión, aprobada): llamada barata a `CHAT_MODEL` con salida estructurada (`is_fastapi: bool`, `reason`), cuenta en el presupuesto. Claramente no-FastAPI → "no sé" sin gastar embeddings.
- **buscar:** vía cliente MCP (`search_docs`, top `TOP_K`).
- **evaluar contexto:** mejor distancia > umbral → "no sé".
- **responder:** el flujo actual (`answer_question`, salidas estructuradas, `validate_citations`, `grounded`).
- **no sé:** respuesta explícita de que no está en la documentación, `grounded=false`, `citations=[]`, `route="no_se"`, `reason` (`out_of_domain` | `insufficient_context` | otro que defina el builder).
- **Presupuesto agotado:** se verifica antes de gastar; `/ask` sigue devolviendo 429.
- Diagrama Mermaid exportado del grafo (API de LangGraph verificada) y pegado en el README.

### 5.7 `/ask`
- Usa el grafo por dentro. Mantiene todos los campos y códigos actuales; añade `route` (`answer` | `no_se`) y `reason` (null cuando responde). `usage` incluye los tokens del clasificador (clave nueva, sin quitar las existentes).
- El workflow n8n y sus smokes siguen funcionando sin cambios.

### 5.8 Observabilidad (LangSmith — mi decisión, aprobada)
- Activado solo por variables de entorno (las oficiales de LangSmith, verificadas). Sin configurar → todo funciona igual, sin errores ni warnings ruidosos.
- Cada pregunta del grafo muestra nodos recorridos, tokens, latencia y costo estimado; las herramientas MCP aparecen como runs propios.
- El dueño crea la cuenta y pone la key en `.env` (nunca en chat; los agentes no editan `.env`).

### 5.9 `scripts/demo_check.py`
- Corre las preguntas de la demo contra el grafo y verifica la ruta esperada (momento 1 verifica `list_sources` vía cliente MCP; 2 → `answer` con cita a la sección de OAuth2 y `get_section` usado; 3 → `route="no_se"` con `reason="out_of_domain"` (lo decide el clasificador antes de buscar)). La parte de Claude del momento 3 no la puede ejecutar el script: `demo_check` imprime debajo de la tabla un checklist manual de ensayo ("la respuesta de Claude no explica cómo configurar permisos de DRF; a lo sumo dice que se menciona como inspiración") — mi decisión.
- `--q "..."` corre una sola pregunta (uso en vivo en el momento 3).
- Salida con **rich**: tabla con columnas **pregunta, ruta, herramientas usadas, tokens, costo USD, latencia ms, ✓/✗**; debajo resumen: **costo total, latencia promedio y "N tests passed"** (corre pytest contra la base de tests).
- Costo = tokens × precio por modelo; precios en variables de entorno con los valores públicos actuales por defecto.
- Respeta el presupuesto; código de salida ≠ 0 si alguna ruta no coincide.

### 5.10 Tests
- Cada nodo y cada ruta: pregunta normal, fuera de dominio, contexto insuficiente, presupuesto agotado.
- Herramientas MCP, reconexión/timeout del cliente, integración grafo↔MCP, test de OAuth2 con código.
- Los 52 existentes siguen pasando.

## 6. Decisiones a registrar (mínimo)
D21 umbral con datos (incluye distancias Django vs OAuth2) · mencionado vs documentado (caso Django) · variante de `docs_src` y marcado de `hl` · troceado sin partir código / bloques gigantes · tabla `sections` · base de tests separada · MCP nuevo vs MCP de n8n · razonamiento en el cliente (no `ask_docs`) · cliente MCP de sesión única + reconexión/timeout, costo vs `retrieve.py` · clasificador LLM vs reglas · LangSmith vs Langfuse · contrato extendido de `/ask` · versiones de LangGraph/MCP/LangSmith verificadas.

## 7. Hecho cuando
- Grafo detrás de `/ask` con su diagrama en el README; n8n intacto.
- Servidor MCP conectado desde Claude Code con las 3 herramientas y logs legibles; `get_section` de OAuth2 muestra código.
- El grafo consume ese mismo servidor como cliente MCP.
- `demo_check.py` muestra ✓ en los 4 momentos.
- Trazas visibles en LangSmith (grafo y herramientas).
- Todos los tests pasan sin tocar la base de la demo; decisiones nuevas en `docs/decisiones.md`.
- Al final: 5 preguntas de entrevista, una por una, corrigiendo al dueño.

## 7.1 Decisiones del revisor de diseño (mis decisiones, marcadas como tales)
- **Re-ingesta:** antes de re-ingestar, `pg_dump` de la base `docs` a `data/` (git-ignorado) como respaldo. `replace_corpus` ya reemplaza los fragmentos del `source_ref` en una transacción; se extiende para reemplazar también `sections`. `INGEST_MAX_TOKENS` (2M) cubre de sobra lo esperado (~200–300k); si se excediera, la ingesta aborta como hoy y se reporta, no se sube el límite sin preguntar.
- **Presupuesto del servidor MCP:** el servidor sabe quién lo lanzó por la variable de entorno `MCP_BUDGET_SCOPE=mcp|ask` leída al arrancar (default `mcp`; valor inválido → el servidor no arranca, con mensaje claro); ese valor es el `kind` con el que registra y verifica embeddings (límite para `mcp`: `MCP_DAILY_TOKEN_BUDGET`, default 100 000; para `ask`: `ASK_DAILY_TOKEN_BUDGET`). La API lanza su servidor con `MCP_BUDGET_SCOPE=ask` explícito en el entorno del subproceso para que todo `/ask` siga contando en el presupuesto de `ask`; Claude usa `mcp`, así la demo no se come el presupuesto de n8n. Sin cambio de esquema (`kind` ya es texto). El servidor lee `.env` del repo y `DATABASE_URL` del entorno, así los tests lo apuntan a `docs_test`. **Test:** con `MCP_BUDGET_SCOPE=ask` el uso de `search_docs` queda en `kind=ask`; sin la variable, en `mcp`; con un valor inválido el servidor no arranca.
- **Momento 1 en `demo_check`:** llama `list_sources` directo por el cliente MCP; el grafo no gana una ruta "meta".
- **`get_section` en el grafo:** criterio determinista — tras `search_docs`, si la ruta sigue a "responder", el nodo pide `get_section` del mejor resultado y lo añade al contexto. Así el momento 2 siempre lo usa.
- **URLs:** `sections` usa exactamente las mismas URLs (con ancla) que `chunks`. La URL sin ancla es la intro de la página; `get_section` sobre ella devuelve la intro más la lista de secciones de la página.
- **Presupuesto en `/ask`:** se verifica antes del clasificador y otra vez antes de responder; el uso del clasificador se registra también en la ruta "no sé".

## 8. Lo que queda al builder
Forma exacta del marcado de `hl`; criterio para que "buscar" llame `get_section`; textos exactos de descripciones e `instructions`; estructura de módulos (sugerencia: `src/docs_agent/mcp_server/`, `src/docs_agent/agent/`); valores por defecto de timeouts.
