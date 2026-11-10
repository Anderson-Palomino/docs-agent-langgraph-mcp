# Decisiones técnicas

Registro para estudiar y explicar en entrevistas. Cada entrada: **qué se eligió**,
**alternativas**, **por qué** y, cuando aplica, **cuándo revisarla**.

---

## Semana 1 — RAG con citas

### D1. Corpus: documentación de FastAPI (inglés, versión fijada)
- **Elegido:** los Markdown de `fastapi/fastapi` → `docs/en/docs/`, de un tag de release fijo.
- **Alternativas:** documentación de AWS SQS; varias documentaciones a la vez.
- **Por qué:** la fuente ya está en Markdown (no hay que raspar HTML), cada archivo
  corresponde a una URL pública de `fastapi.tiangolo.com` (es la cita) y la licencia es
  MIT. Además conozco FastAPI, así que puedo juzgar si una respuesta o cita es correcta,
  lo que importa para el golden set de la Semana 3. Fijar el tag hace la ingesta
  reproducible. SQS habría implicado scraping de HTML, más frágil.
- **Revisar si:** quiero mostrar un dominio "enterprise" o multi-fuente.

### D2. Idioma: responder en el idioma de la pregunta
- **Elegido:** el corpus, el README y los ejemplos van en inglés; el modelo responde en
  el idioma en que se pregunta.
- **Alternativas:** solo inglés; traducir el corpus.
- **Por qué:** las ofertas objetivo son de LatAm. Preguntar en español y recibir citas a
  la doc en inglés es una buena demo, y `text-embedding-3-small` es multilingüe (la
  búsqueda entre idiomas funciona sin traducir).

### D3. Sin LangChain en la Semana 1: SDK de OpenAI + psycopg directo
- **Elegido:** llamadas directas a `openai` y SQL explícito con `psycopg` + `pgvector`.
- **Alternativas:** `langchain-postgres` PGVector + `RetrievalQA`; LlamaIndex.
- **Por qué:** cada paso del RAG (embeber, buscar por coseno, armar el prompt, validar
  las citas) queda visible y lo puedo explicar línea a línea. En la Semana 2 estas
  funciones se convierten en nodos de LangGraph sin depender de abstracciones de
  LangChain.

### D4. Fragmentos por encabezados Markdown
- **Elegido:** partir por `##`/`###`, con un tope de tamaño y solapamiento al subdividir;
  la cita es la URL + `#ancla` de la sección.
- **Alternativas:** fragmentos de tamaño fijo (por ejemplo 500 tokens) sin mirar la
  estructura; un archivo entero por fragmento.
- **Por qué:** una sección de la doc es una unidad de significado, así que recuperarla
  completa da mejor contexto, y el ancla permite citar la sección exacta y no solo la
  página.

### D5. Esquema con script SQL de init + índice HNSW coseno
- **Elegido:** `db/init.sql` montado en `docker-entrypoint-initdb.d`; columna
  `vector(1536)` con índice HNSW `vector_cosine_ops`.
- **Alternativas:** migraciones con Alembic; índice IVFFlat; sin índice.
- **Por qué:** con un esquema chico y estable, Alembic agrega ceremonia sin beneficio
  todavía. HNSW no necesita entrenarse con datos previos (IVFFlat sí) y tiene buen
  recall por defecto. Uso coseno como opción por defecto más legible: con vectores normalizados (como los de OpenAI) coseno, producto interno y L2 dan el mismo ranking, así que la elección no cambia los resultados.
- **Revisar si:** el esquema empieza a cambiar entre semanas (en ese caso, Alembic).

### D6. Salida estructurada y validación de citas
- **Elegido:** el modelo devuelve `{answer, citations[]}` con salida estructurada, y se
  descarta cualquier cita que no esté entre los fragmentos recuperados.
- **Alternativas:** texto libre con las citas parseadas por regex; confiar en el modelo.
- **Por qué:** evita URLs inventadas (la anti-meta principal) y deja la respuesta lista
  para evaluar la "fuente correcta" en la Semana 3.

### D7. La ingesta es un comando aparte
- **Elegido:** `docker compose run --rm api python -m docs_agent.ingest.run`.
- **Alternativas:** ingerir automáticamente al arrancar la API.
- **Por qué:** la ingesta gasta tokens y tarda. Arrancar la API debe ser rápido y
  gratis, y la ingesta debe ser explícita.

### D8. Python 3.12 + uv
- **Elegido:** `uv` para las dependencias y el lockfile; imagen Python 3.12 slim.
- **Alternativas:** pip + requirements.txt; Poetry.
- **Por qué:** `uv` es rápido, genera un lockfile reproducible y hoy es el estándar
  emergente. 3.12 tiene buen soporte en todas las librerías del stack.

### D9. Tests: OpenAI mockeado; integración contra Postgres real
- **Elegido:** pytest; los unitarios mockean OpenAI y los de integración usan el
  Postgres de compose.
- **Alternativas:** grabar respuestas reales (VCR); usar SQLite.
- **Por qué:** los tests no gastan tokens y son deterministas. pgvector no existe en
  SQLite, así que la búsqueda vectorial se prueba contra la base real.

### D10. Si se descartan todas las citas: `grounded: false`, sin reintento
- **Elegido:** HTTP 200 con la respuesta del modelo, `citations: []` y `grounded: false`.
- **Alternativas:** reintentar el modelo; devolver un mensaje fijo de "no encontré";
  devolver un error 4xx/5xx.
- **Por qué:** nunca se muestra una cita inventada y el cliente sabe que la respuesta no
  tiene respaldo. Decidir qué hacer con eso (la rama "no sé") es justo el trabajo del
  grafo en la Semana 2, así que no lo adelanto aquí. Reintentar duplica el costo sin
  garantía de mejora.

### D11. `uv` en el host, tests unitarios locales, integración contra el Postgres de compose
- **Elegido:** instalar `uv` a nivel de usuario; uv gestiona Python 3.12. `uv run pytest`
  en el host, y los tests de integración (marker `integration`) usan
  `localhost:5434` (puerto del host del servicio `db` de compose; ver D13).
- **Alternativas:** correr todo dentro de contenedores; usar el Python 3.13 del sistema.
- **Por qué:** el ciclo de los tests es mucho más rápido en el host, y uv aísla la
  versión de Python sin tocar la del sistema. La imagen de Docker usa la misma 3.12 y el
  mismo lockfile, así que el entorno local y el contenedor no se separan.

### D12. Identidad git: email noreply de GitHub + trailer de Claude
- **Elegido:** autor `Anderson-Palomino <…@users.noreply.github.com>` configurado solo en
  este repo; los commits llevan `Co-Authored-By: Claude`.
- **Alternativas:** el correo de trabajo (config global); el Gmail personal; commits sin
  trailer.
- **Por qué:** el repo es público y de portafolio. El noreply vincula los commits al
  perfil sin exponer ningún correo, y el trailer refleja con transparencia el flujo
  spec → plan → implementación con Claude Code, que es parte de la historia que voy a
  contar en entrevistas.

### D13. Corpus fijado al tag 0.162.0 de FastAPI y Postgres en el puerto 5434
- **Elegido:** `FASTAPI_DOCS_REF` por defecto = `0.162.0`, el último release estable de
  `fastapi/fastapi` al construir (resuelto con `gh api repos/fastapi/fastapi/releases/latest`).
  El Postgres de compose se expone en el host como `localhost:5434` (dentro de compose
  sigue siendo `db:5432`).
- **Alternativas:** seguir `master`/`latest` en cada ingesta; usar el puerto estándar 5432.
- **Por qué:** un tag fijo hace la ingesta reproducible: el mismo corpus produce los mismos
  chunks y las citas no cambian entre ejecuciones. Se actualiza a propósito, no por
  accidente. El 5434 evita chocar con un Postgres local ya instalado en el 5432 y con el
  Postgres de otro proyecto local que ya ocupa el 5433.

### D14. `connect_timeout=5` en la conexión y `init.sql` solo en volumen nuevo
- **Elegido:** `db.connect()` pasa `connect_timeout=5` a psycopg. Los tests de integración
  capturan `psycopg.OperationalError` y hacen skip. `db/init.sql` solo se ejecuta cuando el
  volumen `pgdata` es nuevo; si el esquema cambia hay que correr `docker compose down -v`.
- **Alternativas:** sin timeout (el default de psycopg); hacer skip ante cualquier `Exception`.
- **Por qué:** en Windows/Docker un host:puerto inalcanzable no rechaza la conexión, la deja
  expirar, así que sin timeout los tests de integración se cuelgan más de 100 s en vez de
  hacer skip. Capturar solo `OperationalError` deja que los bugs de configuración fallen con
  ruido. El entrypoint de Postgres ignora `docker-entrypoint-initdb.d` si ya hay datos, por
  eso un cambio de esquema exige recrear el volumen (ver D5).
  Gotcha IPv6: con el puerto publicado solo en `127.0.0.1`, `localhost` resuelve primero a `::1`
  y cada conexión espera el `connect_timeout` completo (5 s) antes de caer a IPv4 (la suite pasó de
  5 s a 145 s); por eso la URL del host usa `127.0.0.1` y no `localhost`.

### D15. Corpus = 147 páginas del tag, ancla por `{ #id }` con slug MkDocs de respaldo
- **Elegido:** el tarball de GitHub (`codeload`, cacheado en `data/`) trae 156 `.md` en
  `docs/en/docs/`; se excluyen 9 (`release-notes`, `management`, `fastapi-people`,
  `contributing`, `external-links`, `newsletter`, `help-fastapi`, `translation-banner` y
  `_llm-test`, una página interna para probar traducciones) y quedan **147**. El ancla de
  cada heading sale del `{ #id }` explícito (attr_list) cuando existe (995 de 1010 headings
  `##`+ en el tag); si no, se aplica el slug de MkDocs `toc` (15 headings, casi todos en
  `reference/`). Ambas rutas se verificaron contra el HTML real: `#request-body`,
  `#import-pydantics-basemodel`, `#depends` y `#api-key-security-schemes` existen en
  fastapi.tiangolo.com. Los includes `{* ../../docs_src/... *}` (453 líneas en el corpus) se
  dejan tal cual en el texto.
- **Alternativas:** raspar el sitio publicado; resolver los includes inlineando el código de
  `docs_src/`; usar siempre el slug sin mirar `{ #id }`.
- **Por qué:** el tarball de un tag fijo es reproducible y no depende del HTML del sitio.
  Usar el id explícito es obligatorio porque los slugs generados divergen del id (p. ej. en
  traducciones o ids personalizados) y una cita con ancla rota pierde credibilidad. Los
  includes apuntan a archivos fuera de `docs/en/docs/`, que el alcance del corpus no
  incluye; dejarlos es inocuo (son una línea de marcador) y resolverlos agranda los chunks
  con código que el texto ya describe. Se puede revisar si las evaluaciones lo piden.

### D16. Troceado por `##`/`###` con tope de 800 tokens y solape de 100
- **Elegido:** cada sección `##`/`###` (fuera de bloques de código, con fences de ``` o ```` y posible sangría) es un fragmento con su propia URL `#ancla`; la intro antes del primer `##` usa la URL de la página. Si una sección pasa de 800 tokens (cl100k_base) se parte por párrafos acumulando hasta 800, y cada sub-fragmento arranca con las últimas ~100 tokens del anterior (recortadas a límite de palabra). Un párrafo o bloque de código mayor que el tope se deja entero. El tope real es por tanto ~800 + solape (el prefijo de solape no cuenta en el tope). Corpus real: 147 páginas -> 1088 fragmentos, mediana 129 tokens, máximo 1130; solo 5 fragmentos superan 800: en 4 hay un bloque indivisible > 800 tokens, y el quinto (`https://fastapi.tiangolo.com/#opinions`, 805 tokens, bloque más grande 707) lo supera solo por el prefijo de solape; 0 fragmentos cuyo encabezado venga de dentro de un bloque de código. Backlog Semana 2: contar el prefijo de solape dentro del tope.
- **Alternativas:** trocear por tamaño fijo ignorando la estructura; partir también los bloques de código; trocear solo por `##`.
- **Por qué:** cada fragmento corresponde a una sección con ancla propia, así la cita enlaza justo a donde está la respuesta. 800 tokens cabe holgado en el embedding y en el contexto del LLM sin mezclar temas; el solape de 100 evita perder frases en el corte. Partir código lo vuelve inútil, por eso se tolera superar el tope.
- **Nota (Semana 2):** el tope ahora incluye el solape y los bloques de código mayores que el tope se parten por líneas; ver D24 y D25.

### D17. Presupuesto diario de tokens en Postgres, con chequeo previo
- **Elegido:** tabla `token_usage(day, kind, tokens)` con un upsert atómico (`ON CONFLICT (day, kind) DO UPDATE SET tokens = tokens + excluded.tokens`). El "día" es la fecha UTC calculada en SQL (`(now() at time zone 'utc')::date`), no la del servidor. `check_budget` se llama **antes** de cada petición y falla si `used >= limit`; el consumo real se registra después con `record_usage`.
- **Alternativas:** contador en memoria del proceso; Redis; reservar los tokens estimados antes de llamar al modelo; contar el día en hora local.
- **Por qué:** el gasto debe sobrevivir a reinicios y compartirse entre procesos (API, ingesta), y Postgres ya está en el stack, así que no añade dependencias. El upsert evita condiciones de carrera entre lecturas y escrituras. El upsert evita pérdidas de actualización (dos escrituras concurrentes no se pisan), pero el patrón comprobar-y-luego-registrar no es atómico: con N peticiones concurrentes que pasan el chequeo a la vez, el límite puede sobrepasarse hasta en N peticiones (el coste solo se conoce al terminar); es aceptable para un tope de costes de portfolio y evita reservas complejas. UTC hace el reinicio diario determinista en cualquier máquina.

### D18. Ingesta: tope estimado antes de embeber y reemplazo transaccional por versión
- **Elegido:** `run_ingest` suma los `token_count` de los fragmentos y, si supera `INGEST_MAX_TOKENS`, lanza `IngestLimitExceeded` antes de llamar a OpenAI. Los embeddings se piden en lotes de 100. `replace_corpus` hace `DELETE ... WHERE source_ref` + `INSERT` y confirma con un `commit()` explícito (con `rollback()` si algo falla). El uso real (`usage.total_tokens`) se registra al final con `record_usage(KIND_INGEST)`.
- **Alternativas:** `with conn.transaction()` en `replace_corpus`; borrar y reinsertar todo el contenido de la tabla; estimar el coste solo con el uso real tras embeber.
- **Por qué:** el tope previo evita una factura sorpresa por un corpus inesperadamente grande: aborta antes de gastar nada. Reemplazar por `source_ref` en una sola transacción hace la ingesta idempotente y nunca deja la tabla a medias (o está el corpus viejo o el nuevo). `conn.transaction()` se descartó porque, si la conexión ya tiene una transacción de lectura abierta (p. ej. tras `tokens_used_today`), solo crea un savepoint y no confirma; el `commit()` explícito es inequívoco y está cubierto por un test que lee desde otra conexión.
- **Filtro por versión:** `search` y `corpus_size` filtran por `source_ref = FASTAPI_DOCS_REF`. Como `replace_corpus` reemplaza por `source_ref`, al cambiar de versión de docs el corpus anterior sigue en la tabla; sin el filtro `/ask` mezclaría versiones y `/health` las contaría juntas. Cubierto por tests con dos `source_ref`.

### D19. Respuesta estructurada, citas validadas y conexión por petición en `/ask`
- **Elegido:** `client.chat.completions.parse(..., response_format=LLMAnswer, temperature=0)` (openai 3.42.1 ya expone `parse` fuera de `beta`) con esquema `{answer, citations: list[str]}`. Las URLs citadas se validan contra los fragmentos recuperados (comparación exacta tras `strip()`, sin duplicados, orden citado); las que no están se descartan. Si se descartan todas: 200 con `citations: []` y `grounded: false`, sin reintento. Errores `openai.OpenAIError` (clase base: incluye `APIError` y también `LengthFinishReasonError`/`ContentFilterFinishReasonError` de `parse`) en embedding o chat -> 502 sin registrar uso; presupuesto agotado -> 429; corpus vacío (para la versión `FASTAPI_DOCS_REF` configurada) -> 503; `OPENAI_API_KEY` vacía -> 503 `OPENAI_API_KEY not configured`, comprobado antes de llamar a OpenAI. Uso registrado = embedding + prompt + completion tokens. Cada petición abre su propia conexión a Postgres (`get_conn`, se cierra al terminar), sin pool.
- **Cliente OpenAI:** `timeout=30` s y `max_retries=2` (reintentos del SDK con backoff ante 429/5xx/conexión). Sin timeout, el SDK espera hasta 600 s y una petición colgada retendría el worker; 30 s cubre de sobra una respuesta de `gpt-4.1-mini` con 5 fragmentos, y 2 reintentos absorben fallos transitorios sin multiplicar el coste.
- **Alternativas:** pedir JSON libre y parsearlo a mano; reintentar cuando todas las citas son inválidas; pool de conexiones; `temperature` por defecto.
- **Por qué:** la salida estructurada garantiza un esquema válido sin parseo frágil. El modelo puede inventar URLs, así que la cita solo vale si existe en el contexto recuperado: validar en código es lo que hace que "cita" signifique algo. Sin reintento se mantiene el coste predecible y se expone honestamente `grounded: false`. `temperature=0` hace las respuestas lo más reproducibles posible para evaluar. Sin pool en S1: el tráfico es mínimo, abrir una conexión local cuesta milisegundos y evita gestionar ciclo de vida, límites y conexiones obsoletas; se revisará si la latencia lo pide.
- **Prompt de sistema (tal cual):**
  ```
  You answer questions about the FastAPI documentation.
  - Answer ONLY with the information in the numbered context fragments provided.
  - Reply in the same language as the user's question.
  - In `citations`, list the exact URLs (copied verbatim) of the fragments you actually used.
  - If the context is not enough to answer, say you don't know and leave `citations` empty.
  ```
  El mensaje de usuario lleva los fragmentos como `[n] título\nURL: url\ncontenido` y luego `Question: ...`.

### D20. Infraestructura: imagen pg17, HNSW por defecto, Dockerfile y límites de tokens
- **Elegido:** (1) Postgres con la imagen `pgvector/pgvector:pg17`: es la imagen oficial de pgvector sobre Postgres 17 (la última mayor estable al montar el proyecto), con la extensión ya compilada. (2) Índice HNSW con los parámetros por defecto de pgvector (`m=16`, `ef_construction=64`, `ef_search=40`). (3) Dockerfile con `uv` fijado a 0.13.6, `uv sync --frozen --no-dev` (instala exactamente `uv.lock`, sin dependencias de desarrollo), y `DATABASE_URL` sobrescrita a `db:5432` en compose (dentro de la red de compose el puerto es el interno, no el 5434 del host). (4) Límites por defecto: 200.000 tokens/día para `/ask` y 2.000.000 por ingesta.
- **Alternativas:** pg16 o `latest`; ajustar `m`/`ef_construction`/`ef_search`; imagen con `uv` sin fijar o `uv sync` sin `--frozen`; límites más ajustados o más holgados.
- **Por qué:** pg17 es estable y pgvector la soporta; fijar la mayor evita sorpresas con `latest`. Con ~1.000 filas HNSW con los valores por defecto da recall prácticamente perfecto y consultas de milisegundos; afinar parámetros solo tiene sentido con cientos de miles de vectores y con evaluaciones que midan el recall (Semana 2+). Fijar `uv` y usar `--frozen` hace el build reproducible: la imagen instala lo mismo que probé en local. 200.000 tokens/día para `/ask` son del orden de 100 preguntas al día (cada una gasta ~2.000 tokens entre embedding, contexto y respuesta), suficiente para una demo y un tope de coste duro. La ingesta real consume 181.350 tokens, así que 2.000.000 deja ~10x de margen para crecer el corpus pero aborta ante un error grosero (p. ej. apuntar a un repo enorme).
- **Deuda reconocida (backlog Semana 2):** el contenedor `api` corre como root y no tiene healthcheck; se acepta en Semana 1 por ser un entorno local de portfolio.
- **Revisar si:** se despliega fuera de local (usuario no root, healthcheck, secretos), o el corpus crece lo bastante como para medir recall de HNSW.

### D21. Umbral de "no sé": distancia coseno 0.52
- **Elegido:** `Settings.no_answer_distance_threshold = 0.52` (env `NO_ANSWER_DISTANCE_THRESHOLD`). Si la mejor distancia coseno del top-k supera el umbral, el agente responde "no sé" sin llamar al LLM. Calibración con 20 preguntas (10 dentro, 10 fuera; ES/EN) contra `docs` 0.162.0, mejor chunk (k=1); tabla completa en `docs/calibracion-umbral.md`. Filas clave: pregunta OAuth2 de la demo 0.4608 (`/tutorial/security/get-current-user/`); pregunta Django REST Framework de la demo 0.6010 (mejor chunk `/alternatives/#django-rest-framework`, una página que solo menciona DRF); peor "dentro" 0.4683 (TestClient); mejor "fuera" 0.5273 (ORM de Django, cae en `/tutorial/body/`); punto medio 0.498. Rango "dentro" 0.2849-0.4683; rango "fuera" 0.5273-0.8715.
- **Alternativas:** 0.50 (punto medio; deja ~0.03 sobre la peor válida); 0.45 o menos (rechaza preguntas válidas como OAuth2 y TestClient); 0.55-0.60 (deja pasar más preguntas de fuera). Si el umbral es demasiado alto, preguntas fuera del corpus con contexto pobre llegan al LLM y se arriesga a inventar; si es demasiado bajo, preguntas válidas reciben "no sé".
- **Por qué:** los errores son asimétricos. Un falso "no sé" a una pregunta válida no tiene otra capa que lo corrija, mientras que una pregunta de fuera que pase el umbral todavía tiene el clasificador del grafo y la regla "mencionar no es documentar". Por eso priorizamos el margen de las preguntas válidas: 0.52 deja ~0.05 sobre la peor válida frente a ~0.03 con 0.50.
- **Limitaciones:** solo 20 preguntas; el margen total entre grupos es 0.059; la pregunta del ORM de Django queda a 0.007 del umbral (0.5273 vs 0.52) y la protege el clasificador, no la distancia.
- **Pendiente:** recalibrar en la Semana 3 con el golden set de 30 preguntas.

### D22. Base de tests separada (`docs_test`)
- **Elegido:** los tests usan siempre la base `docs_test`, en el mismo contenedor Postgres que la demo (`docs`). `Settings.test_database_url` (override con `TEST_DATABASE_URL`) alimenta un fixture autouse que fija `DATABASE_URL`; un fixture de sesión crea `docs_test` si falta (conexión autocommit a la base `postgres`) y aplica `db/init.sql`. Si Postgres no responde, no falla y los tests de integración se saltan como antes. `db_conn` sigue truncando, pero ahora solo `docs_test`.
- **Alternativas:** un contenedor Postgres aparte para tests; testcontainers; seguir truncando `docs` y re-ingestar tras cada corrida.
- **Por qué:** antes cada `pytest` vaciaba la base de la demo (1088 chunks, ~181k tokens de embeddings que cuestan dinero re-generar). Una segunda base en el mismo servidor da aislamiento total de datos sin coste de infraestructura: `CREATE DATABASE` es instantáneo y reutiliza el compose existente. Un contenedor aparte duplicaría puerto, volumen y configuración para un aislamiento que aquí no aporta más; testcontainers añade una dependencia y arrancar un contenedor por sesión (segundos, y exige Docker accesible desde el test) para un proyecto de un solo desarrollador con compose ya levantado.
- **Revisar si:** los tests corren en CI sin compose (ahí testcontainers o un service container sí compensan), o necesitan una versión de Postgres/extensiones distinta de la demo.

### D23. Includes de `docs_src`: se resuelve solo el archivo nombrado, `hl` como comentario
- **Elegido:** cada `{* ../../docs_src/<ruta> ln[..] hl[..] *}` se reemplaza por un bloque ```` ```python ```` con el contenido de **ese** archivo (en 0.162.0 casi siempre la variante `_an_py310`). `ln[a:b,c]` recorta líneas (1-based, inclusivas, fuera de rango se recorta) y pone `# ...` entre rangos no contiguos; `hl[..]` usa números del archivo original y marca cada línea resaltada con el sufijo `  # highlight`. Una ruta ausente deja `[code example: <ruta> not available]` fuera de fence y se cuenta como no resuelta. `fetch_docs` lee `docs_src/**` del mismo tarball y registra en stderr `resolved N includes, M missing`. Sobre el tarball real: 453 includes, 452 resueltos y 1 faltante (`how-to/configure-swagger-ui.md` apunta a `../../fastapi/openapi/docs.py`, código fuente de la librería y no ejemplo de `docs_src`).
- **Alternativas:** añadir también las variantes hermanas (`_py310`, `_py39`, sin `_an`); dejar los includes sin resolver; marcar `hl` con comentarios distintos o ignorarlo.
- **Por qué:** sin resolver, el índice no contiene el código (las páginas solo tienen el placeholder) y el RAG no puede responder preguntas de "cómo se escribe". La variante nombrada es la que la doc muestra por defecto; agregar las hermanas duplicaría casi el mismo código varias veces en el índice y sesgaría la búsqueda hacia esos ejemplos repetidos. `# highlight` conserva en texto plano la señal de "esta es la línea clave" que en la web se ve como resaltado, sin romper la sintaxis Python.
- **Revisar si:** las preguntas necesitan versiones antiguas de Python (variantes `_py39`), o el recorte con `# ...` confunde al modelo.

### D24. Troceado: tope con solape y bloques de código
- **Elegido:** `CHUNK_MAX_TOKENS=800` es un tope real: cuenta también el prefijo de solape (si prefijo + bloque no caben, ese fragmento va sin solape). El solape nunca se toma de dentro de un bloque de código (si la cola cae dentro de uno o contiene una fence, sin solape). Ningún bloque de código queda abierto en un fragmento y cerrado en otro, **salvo** un bloque que por sí solo exceda el tope: ese se parte por líneas, cada trozo se cierra con la misma fence y el siguiente la reabre (```` ```python ````) seguida de la línea `# (continued)`; una línea que sola no cabe se parte por tokens (no ocurre en el corpus). Esto **revierte la regla de D16** ("un bloque mayor que el tope se deja entero") **solo para los bloques mayores que el tope**. Además `split_sections(doc)` devuelve cada sección completa (`Section(url, title, content)`, sin tope) con las mismas URLs y títulos que los fragmentos (misma función interna), para `get_section`.
- **Números (tarball 0.162.0):** W1: 147 páginas -> 1088 fragmentos, mediana 129, máximo 1130. Con los includes de D23 y el troceado viejo: 1118 fragmentos, mediana 163, máximo 2679, 18 sobre 800. Con este troceado: 1128 fragmentos, mediana 164, máximo 800, 0 sobre 800; 17 bloques de código partidos (20 fragmentos empiezan con `# (continued)`), 0 fragmentos con fences desbalanceadas, 0 párrafos de texto mayores que el tope. `split_sections`: 1070 secciones, mismo conjunto de URLs que los fragmentos.
- **Alternativas:** mantener D16 y tolerar fragmentos de hasta ~2700 tokens; truncar el bloque; partir el bloque por funciones/clases con un parser de Python; resumirlo.
- **Por qué:** los dos requisitos ("no partir bloques de código" y "no pasar de 800") solo chocan en esos 17 bloques, que con los includes resueltos llegan a 2679 tokens: un fragmento así diluye el embedding y se come el contexto del LLM. Gana el tope, pero el corte queda en límites de línea y con la fence reabierta, así cada trozo sigue siendo Markdown válido y código legible; `# (continued)` avisa al modelo de que falta el principio, y la sección entera sigue disponible vía `split_sections`. Truncar perdería código; un parser por funciones solo sirve para Python y no garantiza el tope.

### D25. Tabla `sections` para `get_section`
- **Elegido:** tabla `sections (id, source_ref, url, title, content, UNIQUE (source_ref, url))` poblada en la misma ingesta con `split_sections`. `replace_corpus` reemplaza chunks y sections del `source_ref` en una sola transacción (si falla una, no cambia ninguna). `db/init.sql` sigue idempotente; como solo corre en volumen nuevo (D14), se aplicó a la base existente con `psql -U docs -d docs < db/init.sql` tras un `pg_dump` de respaldo.
- **Alternativas:** reconstruir la sección uniendo los fragmentos de la misma URL en el momento de la consulta; guardar la sección solo como columna extra en `chunks`.
- **Por qué:** los fragmentos se solapan (100 tokens) y los bloques de código largos se parten con fences reabiertas y `# (continued)` (D24); concatenarlos obliga a deduplicar el solape y deshacer esos cortes, con riesgo de duplicar o perder texto. Una fila por sección entrega exactamente el Markdown original y `get_section(url)` es una lectura por clave única. El costo es ~1070 filas de texto sin embedding, despreciable.
- **Números (re-ingesta real, 0.162.0):** 147 páginas -> 1128 fragmentos (mediana 164, máximo 800 tokens) y 1070 secciones; 248997 tokens de embedding; includes: 452 resueltos, 1 faltante (D23). Sin abortar por `INGEST_MAX_TOKENS`.
- **Revisar si:** el corpus crece lo bastante como para que duplicar el texto (chunks + sections) importe, o si hay URLs repetidas dentro de una versión (la restricción UNIQUE lo haría fallar).
