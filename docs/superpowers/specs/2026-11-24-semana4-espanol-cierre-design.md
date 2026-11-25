# Semana 4 — Preguntas en español, cierre de pendientes y README final (diseño)

Fecha: 2026-11-24 · Rama: `feat/semana4-espanol-cierre` (worktree `C:\dev\docs-agent-langgraph-mcp-semana4`, desde `main` 7b062e8) · Punto de partida: `C:\Users\ander\Downloads\SEMANA4_PLAN.md` (plan del dueño) + respuestas del brainstorming.

## 1. Intención

El dueño está en entrevistas y los entrevistadores en Perú prueban la demo en español. Hoy 4 de las 9 preguntas válidas en español del golden set reciben "no sé" (g03, g06, g07, g09; distancias 0.59–0.67 > umbral 0.52) porque `text-embedding-3-small` no acerca la pregunta en español al corpus en inglés (D36). Arreglar eso es la prioridad; después, cerrar los dos pendientes de verificación de la Semana 3 (coincidencia del juez, D38; clave del límite por IP, D37) y dejar el README en inglés y el guion del video para el reclutador.

**Prioridad, en este orden:** español → pendientes de verificación (juez y límite por IP) → README y demo. Si algo no entra, se documenta y pasa a la semana 5.

## 2. Objetivos, no-objetivos, anti-objetivos

**Objetivos:**
- Traducción al inglés dentro del clasificador, usada solo para buscar (D40).
- Holdout en español de 6 casos en su propio archivo, reportado aparte.
- Tabla antes/después con la ruta del clasificador incluida; revisión del umbral con el criterio de D21.
- Hoja de revisión del juez con "¿de acuerdo? sí/no + nota" y cálculo de coincidencia cuando el dueño la llene.
- Log de la clave resuelta en el 429 e instrucciones para verificarla en Render.
- README final en inglés, `docs/demo-script.md`, checklist de `PLAN.md`.
- Despliegue con verificación externa, solo con aprobación del dueño.

**No-objetivos:**
- Cambiar el modelo de embeddings o re-ingerir el corpus (opción D, descartada).
- Construir la búsqueda doble (opción C): solo se mide una vez, offline.
- Cambiar el prompt de respuesta o el umbral para que la evaluación salga mejor.
- Configurar LangSmith en Render (sigue pendiente en `PLAN.md`; lo configura el dueño si quiere).
- Grabar el video (lo graba el dueño).

**Anti-objetivos (fallaría aunque "funcione"):**
- que el clasificador empeore su ruta en los 30 casos al pedirle la traducción y no se vea;
- que una pregunta en inglés pague una llamada extra o se busque con algo distinto a la pregunta original;
- que un fallo o vacío de la traducción rompa el grafo;
- ajustar el prompt de traducción o el umbral mirando el holdout;
- que la respuesta salga en inglés a una pregunta en español;
- loguear IPs completas o el texto de las preguntas en los logs de Render;
- romper `/ask` (contrato y códigos 422/429/502/503), el servidor MCP, la integración n8n, el despliegue o los 308 tests;
- desplegar sin que el dueño apruebe la evaluación antes/después;
- llenar la hoja del juez en lugar del dueño.

## 3. Restricciones globales

- Flujo superpowers completo; commits pequeños; pytest en cada paso. Los tests nunca llaman a OpenAI ni a LangSmith (LLM mockeado).
- Decisiones nuevas en `docs/decisiones.md` desde D40 (Elegido / Alternativas / Por qué, en español). Cambios a D37/D38 como secciones agregadas, sin reescribir la historia.
- Verificar en la documentación oficial toda API nueva antes de usarla (en particular: campos opcionales/nullables en Structured Outputs de OpenAI con `chat.completions.parse`).
- Presupuesto: la evaluación corre con el kind `eval` (D39) y `--max-tokens`; la traducción ya se cuenta en los tokens del clasificador.
- **Nunca leer, imprimir ni editar `.env`**; nunca imprimir un objeto `Settings`. El `.env` del worktree es una copia hecha con `cp`, sin leerla.
- **No crear cuentas ni manejar credenciales.** Las variables de producción las configura el dueño en Render.
- Solo datos públicos (corpus FastAPI 0.162.0). Nada de BaldeCash, GENIA ni clientes.
- Evaluación contra la base local (`127.0.0.1:5434`), nunca contra producción.
- Firma: autor con la config local del repo; trailer `Co-Authored-By: Anderson Palomino <andersonpalominosandoval@gmail.com>`; nunca un trailer de Claude ni "Generated with Claude Code" en el PR.
- `git add` con rutas explícitas; sin `git stash`; `gh` con `GH_TOKEN=$(gh auth token --user Anderson-Palomino)`, nunca `gh auth switch`.

## 4. Orden de trabajo y pausas

1. **Holdout propuesto** (`eval/holdout_es.json`) + tabla de validación → **pausa 1: el dueño valida `expected_urls` y rutas.** Mientras tanto se avanza con el código de los pasos 2 y 4 (no gastan).
2. Traducción en el clasificador (TDD) + campos nuevos en la evaluación + script de comparación.
3. Corridas reales: golden set completo con juez (con hasta 2 ajustes del prompt, 5.2bis) → prompt congelado → holdout una sola vez → medición de C → calibración offline → tabla antes/después, D40 (y D41 si el umbral cambia) → **pausa 2: el dueño aprueba la evaluación antes de desplegar.**
4. Log del 429 (TDD) + instrucciones de verificación en Render.
5. Hoja del juez armada sobre la corrida nueva (5.6) → **pausa 3: el dueño la llena (~20 min). No se llena por él.** Con sus respuestas: coincidencia, D38 y README.
6. README final, `docs/demo-script.md`, `PLAN.md`.
7. Code review → PR → (aprobado en pausa 2) **el dueño mergea** tras confirmar en el panel de Render que el servicio despliega `main` automáticamente → Render despliega → verificación externa → el dueño prueba el 429 y se cierra D37.

Las pausas 2 y 3 no se bloquean entre sí: si el dueño no ha llenado la hoja del juez, el PR se puede mergear con D38 marcando la coincidencia como pendiente, y se completa en un PR corto después. Si la verificación del 429 no se hace esta semana, D37 queda con "qué falta" documentado.

## 5. Diseño

### 5.1 Traducción dentro del clasificador (D40, opción A)

- `Classification` gana un campo `search_query: str | None`. El prompt dice: si `language` es `"es"`, `search_query` es la pregunta traducida al inglés, fiel (sin responderla ni ampliarla, conservando nombres de código como `Depends`, `status_code`, `Query`); si es `"en"`, `null`. El modelo, la temperatura y el resto del prompt no cambian.
- El nodo `classify` decide la consulta de búsqueda y la guarda en el estado como `search_query` (la consulta **efectivamente usada**, siempre un `str`):
  - `language == "es"` y traducción no vacía tras `strip()` → la traducción;
  - `language == "en"` (aunque el modelo haya devuelto traducción) → la pregunta original;
  - traducción `None`, vacía o solo espacios → la pregunta original;
  - rechazo del modelo (`parsed is None`) → sigue igual que hoy (fuera de dominio, `en`), sin traducción.
  - Además se guarda `translated: bool` (si se buscó con traducción) para la evaluación y la traza.
- El nodo `search` llama a `search_docs` con `state["search_query"]`. El servidor MCP no cambia.
- El nodo `answer` sigue usando `state["question"]` (la original): la respuesta sale en el idioma del usuario. `no_se` no cambia.
- "Detectar el idioma barato": no hay detector nuevo; el clasificador ya corre en todas las preguntas y ya devuelve `language`. Una pregunta en inglés no paga nada extra salvo los pocos tokens del prompt más largo.
- Si la llamada del clasificador falla con excepción, el comportamiento es el de hoy (no se agrega manejo nuevo): la traducción no es una llamada aparte que pueda fallar sola.
- **Trazas:** `search_query` y `translated` quedan en el estado final del grafo, que LangSmith registra como outputs de la corrida `ask` (D34). La evaluación los copia a cada fila del JSON de resultados. No se agregan al contrato de respuesta de `/ask` ni a los logs de Render (texto de usuario).
- **Tests (LLM mockeado):** español con traducción → `search_docs` recibe la traducción y `answer_question` la original; inglés → `search_docs` recibe la original y no hay traducción; `en` con traducción devuelta → se ignora; traducción `None`/`""`/`"  "` → original; fuera de dominio → no busca; los tests existentes del grafo y del clasificador siguen pasando.

### 5.2 Evaluación antes/después

- `evaluate.py` agrega a cada fila `language`, `search_query` y `translated`. El "antes" es `eval/results/2026-11-17.json` (no se vuelve a correr).
- La corrida "después" del golden set (30 casos, con juez) se guarda como `eval/results/2026-11-24.{json,md}`.
- Nuevo `scripts/compare_runs.py ANTES.json DESPUÉS.json` → markdown con, para cada corrida: ruta total, **ruta del clasificador** (`is_fastapi` contra `expected_route`: un caso `no_se` fuera de dominio cuenta como acierto del clasificador si lo cortó; uno `answer` si lo dejó pasar), falsos "no sé", falsos "respondí", citas válidas, acierto de fuente, fidelidad, latencia p50/p95 y costo por pregunta (con y sin juez); y un detalle de g03, g06, g07 y g09 (distancia, ruta, consulta usada, fuentes) antes y después. Reutiliza `evaluation/metrics.py`. Sale en `eval/results/2026-11-24-comparison.md`.
- Casos `either` y `judge_review` se tratan como en la Semana 3.
- La tabla tiene una fila con nombre propio para **las preguntas en español fuera del corpus** (`lang: "es"`, `expected_route: "no_se"`: g19, g22, g25, g26 y g27 del golden set —g25 hoy está a 0.41 y solo la corta el clasificador—, y g30 `either` en la misma fila con su ruta; más las 2 del holdout en su tabla aparte): ruta obtenida, quién la cortó (clasificador o umbral) y distancia. Es el riesgo nuevo de la traducción.
- Cuando el clasificador corta un caso, la búsqueda extra que `evaluate.py` hace solo para registrar distancias usa la misma consulta que el grafo habría usado (`search_query`: la traducción si es `es`), no la pregunta original, para que las distancias en español sean comparables entre `answer` y `no_se` (decisión del builder).

### 5.2bis Ajustes del prompt y criterio para desplegar (decidido por el dueño)

- **Criterio para desplegar** (lo aprueba igual el dueño en la pausa 2), medido en el golden set: (1) la ruta del clasificador en los 30 casos no empeora respecto del 11-17; (2) ningún falso "respondí" nuevo, revisando aparte la fila de español fuera del corpus; (3) al menos 3 de g03, g06, g07, g09 pasan a `answer`.
- Si la primera corrida no cumple, se puede ajustar el prompt de traducción **como máximo 2 veces** mirando solo el golden set (~US$0.04 por corrida); cada ajuste queda en D40 con su motivo y su resultado.
- Si después del segundo ajuste no se cumple: **no se sigue probando**. D40 documenta qué falló y por qué, el español pasa a la semana 5 y no se despliega la traducción (el resto de la semana sigue).
- Al terminar (cumpla o no), el prompt se congela y recién entonces corre el holdout, una sola vez.
- Se reportan dos cifras por separado: golden set (ajustado, hasta 2 veces) y holdout (una corrida, prompt congelado). En el README la medición limpia que se presenta es la del holdout.

### 5.3 Holdout en español

- `eval/holdout_es.json`, mismo esquema que `golden_set.json`, ids `h01`–`h06`, todos `lang: "es"`: 4 `answer` con `expected_urls` de páginas del corpus distintas a las del golden set donde sea posible, y 2 `no_se`, uno lejano y uno **cercano** (Django o Flask en español, p. ej. cómo definir un blueprint en Flask).
- Tabla de validación para el dueño con `golden_review.py --golden eval/holdout_es.json --out eval/holdout_es_review.md` (si el script no soporta el archivo tal cual, se adapta mínimo).
- **Reglas:** no se usa para ajustar nada (ni el prompt de traducción ni el umbral). Se corre una sola vez después de fijar el prompt, con `evaluate.py --golden eval/holdout_es.json` (con juez), salida `eval/results/2026-11-24-holdout.{json,md}`, y se reporta en una tabla propia, nunca sumado al golden set. Si un caso del holdout falla, se documenta, no se corrige el prompt.
- La calibración del umbral (`calibrate_threshold.py --from-results`) usa solo el golden set.

### 5.4 Medición de la opción C (sin construirla)

- `scripts/measure_dual_query.py`: para los casos `es` de la corrida "después" que tengan `search_query`, llama a `search_docs` (mismo camino MCP, kind `eval`) con la original y con la traducción y anota ambas `best_distance`, la URL top y si la mejor distancia vendría de la original. Una sola corrida; el resultado va como tabla en D40. Costo: solo embeddings (~US$0.0001).

### 5.5 Umbral (criterio D21)

- Con las distancias nuevas se regenera `docs/calibracion-umbral.md`. Se mantiene 0.52 salvo que la tabla muestre otro valor que, con el criterio asimétrico de D21 (un falso "no sé" es el error más grave en la capa del umbral), sea claramente mejor sin aumentar los falsos "respondí" que no corta el clasificador. Si cambia, D41; si no, una línea en D40 con la tabla.

### 5.6 Hoja de revisión del juez (pendiente de D38)

- **Sobre la corrida nueva** (decidido por el dueño): la hoja es `eval/results/2026-11-24-judge-review.md`, generada desde la corrida final del golden set (`2026-11-24.json`, la del prompt congelado). Se borra la hoja vieja `2026-11-17-judge-review.md` (de puntaje 0–1, sin llenar) y el generador de `evaluate.py` pasa al formato nuevo, para que no exista una hoja en el formato viejo.
- Casos: los marcados `judge_review` en el golden set (g01, g02, g10, g12, g16, g30; la marca es fija del golden set, no depende de la corrida) **más** g03, g06, g07 y g09 si ahora se responden (son las respuestas que verán los entrevistadores). Como máximo son 10; si por algún motivo pasan de 10, se avisa al dueño antes de armarla. Si alguno de los 6 marcados no se responde en la corrida nueva, se anota en la hoja y no se reemplaza por otro.
- Por caso: pregunta, ruta, respuesta del modelo, y una tabla de **las afirmaciones que extrajo el juez** con columnas `#`, `afirmación`, `veredicto del juez (apoyada/no)`, `¿de acuerdo? sí/no`, `nota`. Debajo, el contexto que vio el modelo: un extracto de ~1500 caracteres por fragmento visible y el texto completo dentro de un `<details>` plegable (decisión del builder: leer rápido sin perder la fuente completa).
- Se publica y se **espera al dueño**. Con la hoja llena, `--score` (o una función en el mismo script) calcula la coincidencia por afirmación (sí / total) y por caso (caso de acuerdo si todas sus afirmaciones lo están). D38 recibe una sección "Coincidencia con revisión manual" y el README reporta la fidelidad con ese respaldo, o explica dónde falló el juez.

### 5.7 Límite por IP: log del 429 (pendiente de D37)

- `client_ip` se extiende (o se agrega una variante) para devolver también qué entrada de `X-Forwarded-For` se usó: índice desde la derecha, total de entradas, o "peer" si se usó el socket.
- En el 429 de `/ask`, un `logger.warning` con: clave enmascarada (IPv4: dos primeros octetos, `181.65.x.x`; IPv6: los primeros 32 bits del /64, `2800:200:x:x::/64`), índice usado y total de entradas de XFF, y cada entrada de XFF enmascarada igual. Sin pregunta, sin cabeceras completas. Nunca se loguea una IP sin enmascarar.
- Hipótesis a confirmar (de leer el código, no verificada): con `TRUSTED_PROXY_IPS=*` se toma la entrada más a la derecha; si Render agrega un salto intermedio de su borde (p. ej. un proxy CDN) a la derecha del cliente, la clave sería ese salto y cambiaría entre peticiones, lo que explica la anomalía de D37. El log lo confirma o lo descarta.
- Instrucciones para el dueño en `docs/deploy.md` y en el chat: qué petición repetir hasta el 429 (cuántas, a qué URL, desde dos redes), dónde ver los logs en Render (servicio → Logs, buscar el texto del warning) y cómo leer el índice/total. Con lo visto se cierra D37: por cliente, o por salto del proxy y qué ajuste haría falta (p. ej. contar N saltos desde la derecha). El ajuste en sí, si hace falta, es otro paso que se acuerda con el dueño.
- Tests: log en el 429 con IP enmascarada (IPv4 e IPv6), índice/total correctos, ninguna IP completa en el mensaje; sin log en peticiones que pasan.

### 5.8 README, guion y PLAN

- README en inglés para un reclutador técnico que lo lee en 3 minutos: una frase de qué hace; diagrama Mermaid de la arquitectura (API → grafo LangGraph → servidor MCP → Postgres/pgvector, con OpenAI); cómo probar la demo en vivo (URL, una pregunta de ejemplo en español y otra en inglés, aviso del arranque en frío del plan gratis); cómo levantarlo en local; tabla de evaluación actualizada: el holdout como la medición limpia y el golden set aparte, aclarando que su prompt se ajustó mirando esos casos (hasta 2 veces); limitaciones honestas; enlace a `docs/decisiones.md`. La frase "accepts questions in Spanish and English" solo si el punto 1 quedó desplegado.
- `docs/demo-script.md`: guion de 2 minutos por tramos de tiempo: pregunta respondida con citas, pregunta fuera del corpus con "no sé", la evaluación y el servidor MCP en Claude Code (desde `demo/`, D35).
- `PLAN.md`: checklist actualizado.
- Aprovechando el PR: D39 corrige la estimación de ~280k tokens por corrida con lo medido (decisión del builder; cambio de una línea).

### 5.9 Despliegue

- Render despliega `main` automáticamente al mergear (servicio `docs-agent`, rama `main` desde el cierre de la Semana 3). Por eso **mergear = desplegar**: el merge lo hace **el dueño**, después de aprobar la evaluación (pausa 2) y de confirmar en el panel de Render que el servicio sigue en `main` con auto-deploy. Claude no tiene acceso a Render.
- Si el español no cumplió el criterio (5.2bis), el PR que se mergea no activa la traducción (se revierte ese cambio o queda detrás de lo que se acuerde con el dueño en ese momento) y el README no dice que la demo acepta español.
- Sin cambios de variables de entorno ni de esquema: no hace falta re-ingerir Neon.
- Verificación externa tras el deploy: `/health`; una pregunta en español y una en inglés con citas; una fuera del corpus con "no sé" (curl con el cuerpo en un archivo UTF-8 y `--data-binary`, por el codepage de Windows). Resultados en D40 o en `docs/deploy.md`.

## 6. Decisiones nuevas previstas

- **D40 — Preguntas en español.** Elegida A (traducción dentro del clasificador). Alternativas: B (llamada aparte: +1 llamada y +0,4–0,7 s y otra pieza que falla, sin ventaja sobre A); C (búsqueda doble: medida en 5.4, con su tabla); D (embeddings multilingües: `text-embedding-3-large` acepta `dimensions`, así que podría pedirse en 1536 sin cambiar el esquema, y OpenAI reporta mejor recuperación multilingüe [MIRACL 54,9% contra 44,0% en el anuncio de enero de 2024]; se descarta porque exige re-ingerir el corpus, recalibrar el umbral desde cero y la mejora **en este corpus** no está demostrada). Costos y latencias medidos, no estimados, en la versión final. Incluye la ruta del clasificador antes/después y el resultado del holdout.
- **D41 — Umbral**, solo si cambia (5.5).
- **D37** — sección agregada con lo que muestre el log del 429.
- **D38** — sección agregada con la coincidencia juez vs dueño.

## 7. Lo que queda al builder

Nombres internos, la estructura exacta del markdown de comparación y de la hoja del juez, cómo extender `client_ip` sin romper sus llamadores, el texto exacto del prompt de traducción (respetando 5.1), el formato de los logs y la redacción del README y del guion.
