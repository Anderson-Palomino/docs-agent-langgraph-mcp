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

### D26. Servidor MCP propio vs MCP de n8n: conviven
- **Elegido:** un servidor MCP propio (`docs-agent-mcp`, SDK `mcp` 2.3 con `MCPServer`, transporte stdio) con tres herramientas de bajo nivel sobre el corpus: `list_sources`, `search_docs` y `get_section`. Convive con el MCP del workflow de n8n `integrations/n8n/workflows/02-mcp-docs-agent.json`, que expone el agente completo como **una** herramienta HTTP protegida con Bearer. `integrations/n8n/` no se toca.
- **Alternativas:** quedarse solo con el MCP de n8n; reemplazarlo por el servidor propio; exponer el servidor propio por HTTP en vez de stdio.
- **Por qué:** resuelven problemas distintos. El de n8n sirve para integrar el agente ya armado (pregunta -> respuesta con citas) en un flujo o en un cliente remoto. El propio entrega los datos del corpus a un cliente que razona por su cuenta (Claude Desktop/Code, o el grafo): puede buscar, leer la sección entera y decidir. stdio basta para un cliente local, no abre puertos ni necesita autenticación, y un `[mcp] ...` por llamada en stderr deja ver qué pidió el cliente sin ensuciar stdout (el canal MCP).

### D27. Razonamiento en el cliente, sin `ask_docs` en el servidor
- **Elegido:** el servidor solo expone datos (metadatos del corpus, búsqueda, secciones completas). El razonamiento queda en el cliente: Claude o el grafo de LangGraph. Las reglas para el cliente viajan en las `instructions` del servidor (responder solo con lo que devuelven las herramientas, citar la URL exacta, `in_corpus=false` -> "la documentación indexada no lo cubre", "mencionar no es documentar").
- **Alternativas:** una herramienta `ask_docs` que corra el agente completo y devuelva la respuesta.
- **Por qué:** `ask_docs` duplicaría lo que ya hace el MCP de n8n (D26) y convertiría al servidor en cliente de sí mismo: un LLM llamando a una herramienta que llama a otro LLM, con doble coste y una respuesta que el cliente no puede verificar contra las fuentes. Con herramientas de datos el cliente ve las distancias, los fragmentos y la sección completa, y cada token gastado en el servidor es solo de embeddings.

### D28. Mencionado vs documentado
- **Elegido:** el corpus menciona tecnologías que no documenta. Caso Django: aparece en 6 páginas, `alternatives.md` lo nombra 16 veces y "Django REST Framework" aparece 6 veces en `alternatives.md`. En la calibración (D21) el mejor fragmento de la pregunta de la demo sobre DRF es `/alternatives/#django-rest-framework` a 0.6010. `search_docs` puede devolver legítimamente `in_corpus=true` para esas menciones con otras formulaciones, porque es cierto: el texto está en el corpus. Las defensas son el clasificador del grafo y la línea de las `instructions` del servidor ("Mentioning is not documenting: ... say the documentation does not cover it — at most, that it is mentioned — and never fill in from general knowledge"). La pregunta de la demo no se cambia.
- **Alternativas (descartadas):** (1) una lista de páginas "que solo mencionan" para forzar `in_corpus=false`; (2) quitar `alternatives.md` del corpus.
- **Por qué:** la lista está hecha a medida de la demo y no escala: cada tecnología mencionada en cada página nueva pediría una entrada a mano, y el servidor mentiría sobre lo que contiene el corpus. Quitar `alternatives.md` es quitar datos para que la demo pase: perdería una página válida (por qué FastAPI se inspiró en otros frameworks) y el problema volvería con la siguiente mención. La distancia mide parecido de texto, no si la página explica cómo usar algo; esa distinción la hace quien razona (D27).

### D29. `MCP_BUDGET_SCOPE`: el presupuesto depende de quién lanzó el servidor
- **Elegido:** `MCP_BUDGET_SCOPE=mcp|ask` (default `mcp`), leído al arrancar. Si a `docs-agent-mcp` lo lanza Claude, el scope es `mcp` y `search_docs` gasta y se limita contra su propio presupuesto `MCP_DAILY_TOKEN_BUDGET=100000`. Si lo lanza la API (el grafo de `/ask`), el scope es `ask` y gasta contra `ASK_DAILY_TOKEN_BUDGET`, el mismo kind `ask` de `/ask`. Un valor inválido hace fallar `Settings` y el proceso sale con código 1 y `invalid MCP_BUDGET_SCOPE: <valor> (expected mcp|ask)` en stderr. Presupuesto agotado -> error MCP con el mensaje de `BudgetExceeded`, sin llamar a OpenAI.
- **Alternativas:** un único presupuesto compartido para todo; detectar al cliente en tiempo de ejecución; un valor inválido que caiga al default con un warning.
- **Por qué:** sin scope, el uso desde Claude se comería el presupuesto de `/ask` (o al revés) y no se podría ver cuánto gasta cada uno en `token_usage`. Quien lanza el proceso es quien sabe para qué es, así que lo declara por entorno; MCP no da una identidad del cliente fiable para decidirlo. Fallar al arrancar con un valor inválido es mejor que gastar en silencio contra el presupuesto equivocado.

### D30. El grafo consume el servidor por MCP: sesión única, reconexión, timeout; costo frente a `retrieve.py`
- **Elegido:** el grafo de `/ask` llama a `list_sources`, `search_docs` y `get_section` a través del servidor MCP propio (`python -m docs_agent.mcp_server` por stdio, `MCP_BUDGET_SCOPE=ask`) con `DocsMCPClient` (`src/docs_agent/agent/mcp_client.py`): **una** sesión stdio persistente que se abre en la primera llamada y se reutiliza; si el proceso murió, cierra la sesión, reconecta **una vez** y reintenta, y si vuelve a fallar lanza `DocsServerUnavailable`; cada llamada está acotada por `MCP_CALL_TIMEOUT_S=15` (`anyio.fail_after`) y al excederse lanza `DocsToolTimeout` y descarta la sesión (la siguiente llamada reconecta); un `is_error` de la herramienta es `DocsToolError` con el texto del error y no se reintenta. "Proceso muerto" se determinó matando el servidor con `taskkill /F` en Windows: `MCPError(CONNECTION_CLOSED)` entre llamadas o con una llamada en vuelo, `ExceptionGroup` de ese mismo error si muere al arrancar, `OSError` si no se puede lanzar. La sesión vive en una tarea propia porque el SDK exige cerrar el `async with` en la tarea que lo abrió (`RuntimeError: Attempted to exit cancel scope in a different task`), y el grafo llama y cierra desde tareas distintas. Arrancar el servidor también queda acotado por el timeout (un handshake colgado se cancela de inmediato y cuenta como proceso muerto: abrir + un reintento, ~2× el timeout como máximo). Tras `aclose()` el cliente no reabre: `call` lanza `DocsServerUnavailable` y no queda ningún subproceso vivo al apagar la API.
- **Timeouts alineados:** el cliente OpenAI del servidor deriva sus límites de `MCP_CALL_TIMEOUT_S` (`openai_limits` en `mcp_server/__main__.py`): `timeout = T/3` y `max_retries = 1`, así el peor caso (2 × T/3 + ~0,5 s de backoff) termina antes de que el cliente MCP corte la sesión compartida, y queda ~T/3 para Postgres; antes (30 s × 3 intentos frente a 15 s) un embedding lento mataba la sesión antes de que el servidor reintentara. Un `Retry-After` largo de OpenAI (p. ej. en un 429) no lo acota nadie: ese caso termina en `DocsToolTimeout`.
- **Límites conocidos:** el timeout por llamada no incluye el apagado de la sesión descartada (el SDK cierra stdin, espera y mata el árbol: ~2-3 s más en ese camino). La sesión es compartida: un timeout la cierra para todos, y las otras llamadas en vuelo ven el proceso muerto y se reintentan una vez; si una de ellas era `search_docs`, el embedding puede pagarse dos veces (cuenta en el presupuesto igual).
- **Alternativas:** que el grafo llame directamente a `retrieve.py` / `tools.py` en proceso; abrir un proceso por llamada (o por pregunta); `Client(server_instance)` en proceso; reintentos ilimitados o con backoff.
- **Por qué:** un solo servidor para el agente y para Claude significa un solo contrato: las mismas herramientas, las mismas descripciones e `instructions`, el mismo log `[mcp] ...` y el mismo presupuesto por scope (D29). Lo que el grafo ve es exactamente lo que ve Claude, así que una regresión en el servidor aparece en los dos y los evals del grafo validan también lo que consume Claude. Llamar a `retrieve.py` directo sería más rápido, pero tendría dos caminos a mantener en paralelo que podrían divergir sin que nadie lo note. Un proceso por llamada pagaría el arranque cada vez; reconectar una sola vez cubre la caída ocasional del proceso sin esconder un servidor roto detrás de reintentos, y el timeout evita que una pregunta quede colgada si el servidor se bloquea.
- **Costo (medido, `list_sources` sobre la base de la demo, 10 llamadas, mediana, dos corridas):** por stdio con la sesión caliente **55-61 ms**; llamada directa a `tools.list_sources` abriendo una conexión por llamada (lo mismo que hace el servidor) **49 ms**; directa reutilizando la conexión **4 ms**. El transporte MCP (JSON-RPC por pipes) cuesta ~6-12 ms por llamada; el grueso es la conexión a Postgres que el servidor abre en cada herramienta. Arrancar el proceso y hacer el handshake cuesta ~3,5 s una sola vez por sesión. Más un proceso Python extra (~el mismo footprint que la API) mientras la sesión esté abierta.
- **Revisar si:** la latencia por llamada importa frente a los ~1-2 s del LLM (entonces, pool de conexiones en el servidor antes que saltarse MCP), o si `/ask` atiende peticiones concurrentes de forma que una sola sesión se vuelva cuello de botella.

### D31. Clasificador LLM vs reglas por palabras clave
- **Elegido:** un primer nodo `classify` que llama al modelo de chat (`CHAT_MODEL`, `temperature=0`) con salida estructurada `Classification(is_fastapi, language, reason)` (`src/docs_agent/agent/classify.py`). Cuenta como FastAPI todo lo que su documentación cubre (Pydantic en FastAPI, Starlette, seguridad/OAuth2, despliegue, tipado de Python para APIs); cualquier otro framework o tema es `is_fastapi=false` y el grafo va directo a `no_se` con `reason="out_of_domain"` sin buscar ni gastar embeddings. `language` (`es`/`en`, cualquier otro idioma -> `en`) decide el idioma del texto fijo de `no_se`. Se comprueba el presupuesto antes de clasificar, y sus tokens se reportan aparte en `usage` (`classifier_prompt_tokens`, `classifier_completion_tokens`).
- **Alternativas:** reglas por palabras clave ("fastapi", "pydantic", "depends"...) o una lista de frameworks prohibidos; no clasificar y dejar que el umbral de distancia (D21) filtre todo; clasificar con embeddings contra un centroide del corpus.
- **Por qué:** las preguntas reales de FastAPI muchas veces no nombran FastAPI ("¿cómo valido un body?", "how do I add OAuth2 scopes?") y las de otros frameworks comparten vocabulario ("Django REST serializers for request body"): una regla por palabras deja pasar falsos positivos o corta preguntas válidas, y cada caso nuevo es otra regla. El umbral de distancia solo mide parecido semántico, no dominio: una pregunta de Flask sobre rutas puede quedar cerca de los fragmentos de FastAPI y terminar respondida con citas que no aplican. El clasificador cuesta una llamada corta (solo el prompt fijo y la pregunta, sin contexto recuperado) y a cambio corta antes del embedding las preguntas fuera de dominio y deja un `reason` explicable. Las dos defensas se complementan: clasificador para el dominio, umbral para la cobertura.
- **Revisar si:** el costo o la latencia del clasificador pesan frente a la respuesta (entonces, un modelo más chico solo para este nodo), o si los evals muestran falsos negativos en temas límite (ajustar el prompt con ejemplos).

### D32. Por qué un grafo y no una sola llamada al modelo
- **Elegido:** un grafo LangGraph explícito (`src/docs_agent/agent/graph.py`): `START -> classify -> (is_fastapi) search | no_se`; `search -> evaluate -> (best_distance <= umbral) answer | no_se`; `answer -> END`; `no_se -> END`. Cada nodo hace una cosa y devuelve solo lo que cambia del estado (`route`, `reason`, `results`, `usage`, `tools_used`...). `no_se` es un texto fijo, no generado.
- **Alternativas:** una sola llamada al modelo con las herramientas (`search_docs`, `get_section`) y que el modelo decida cuándo buscar y cuándo decir "no sé" (agente ReAct / tool calling libre); el pipeline lineal de la semana 1 (`retrieve -> answer`) con más `if` dentro de la función.
- **Por qué:** en una sola llamada las decisiones importantes (¿es del dominio?, ¿hay contexto suficiente?, ¿qué cito?) quedan dentro del modelo: no se pueden probar ni explicar, y el "no sé" depende de que el modelo se abstenga. En el grafo esas decisiones son **rutas explícitas** en código: fuera de dominio nunca llega a buscar y contexto insuficiente nunca llega al LLM de respuesta, así que esos caminos no gastan tokens de respuesta ni pueden inventar. Cada nodo es **testeable** por separado con dobles (`FakeOpenAI`, `FakeTools`), sin base ni OpenAI: los tests fijan la ruta, el `reason`, las herramientas usadas y los tokens de cada camino. Y con LangSmith activo cada nodo es un paso de la **traza**: se ve en qué nodo se decidió y cuánto costó cada uno, en vez de una caja negra. El costo es más código y una llamada extra (el clasificador); el flujo es fijo y corto, así que no hace falta un agente que planifique.
- **Contexto de la respuesta:** `answer` arma el contexto con el **fragmento completo** de cada resultado top-k (deduplicado por URL) más la sección entera de `results[0]` vía `get_section` (con tope de 12000 caracteres). Para eso el grafo llama a `search_docs` con `include_content=true`, que agrega `content` (el fragmento entero) a cada resultado; por defecto `search_docs` devuelve solo el snippet de 300 caracteres, así el contexto de Claude no crece. Antes el grafo usaba esos snippets, y el contexto quedaba por debajo del de la semana 1, que mandaba el contenido completo de cada fragmento. Si `get_section` falla (URL desconocida, servidor caído, timeout), el grafo registra un `warning` con la URL y el tipo de error y responde solo con los fragmentos completos. Un error de presupuesto no sigue ese camino: se propaga.
- **Revisar si:** las preguntas necesitan varias búsquedas encadenadas o reformular la consulta (entonces, un bucle `evaluate -> search` acotado, o un nodo agente con herramientas dentro del grafo).

### D33. Contrato extendido de `/ask` (`route`, `reason`)
- **Elegido:** `/ask` corre el grafo (D32) por dentro, con las herramientas por el servidor MCP propio (D30): la API crea en el `lifespan` un `DocsMCPClient` perezoso sobre `python -m docs_agent.mcp_server` con `MCP_BUDGET_SCOPE=ask` (D29) y lo cierra al apagar. La respuesta conserva todo lo de la semana 1 (`answer`, `citations` `[{url,title}]`, `grounded`, `usage` con `embedding_tokens`/`prompt_tokens`/`completion_tokens`, `retrieved` con `?debug=true`, ahora tomado de `search_docs`) y **añade** `route` (`"answer"` | `"no_se"`), `reason` (`null` | `"out_of_domain"` | `"insufficient_context"`, siempre presente) y `usage.classifier_tokens` (prompt + completion del clasificador). Errores: los de antes (422, 429, 502 `"Upstream model error"`, 503 sin clave y corpus vacío) más 503 `"Docs server unavailable"` (servidor MCP caído o timeout) y 502 `"Docs tool error"` (otro error de herramienta); `BudgetExceeded` de la API o el error de presupuesto que llega del servidor (`DocsToolError` con "budget") dan el mismo 429 `"Daily token budget exhausted"`. La API registra en `ask` solo lo que gastó ella (clasificador + respuesta) y lo registra **siempre**, también si la petición termina en 429/502/503: los nodos suman a `AgentDeps.spent` cada llamada de chat que volvió (una que falló o no se hizo no cuenta) y la API lo registra en un `finally`; así una caída persistente del servidor MCP no gasta clasificadores sin tocar el presupuesto. Esto cambia la regla de la semana 1 ("sin registrar uso" en los errores): esa regla era cierta porque allí el fallo siempre era la primera llamada; si falla el clasificador se sigue registrando 0. Los embeddings los registra el servidor en el mismo kind. Las consultas a Postgres del endpoint (`check_budget`, `corpus_size`, `record_usage`) van en `asyncio.to_thread`, y también el `check_budget` que los nodos `classify` y `answer` llaman dentro del grafo.
- **Alternativas:** cambiar el contrato (por ejemplo, reemplazar `grounded` por `route`, o devolver un 404/204 cuando el grafo dice "no sé"); un endpoint nuevo (`/agent/ask`) y dejar `/ask` con el pipeline de la semana 1; no exponer la ruta y dejar que el cliente la deduzca de `grounded`.
- **Por qué:** `/ask` ya tiene clientes: los workflows de n8n (`integrations/n8n/workflows/01-ask-log.json` lee `answer`, `grounded`, `citations`, `usage.*_tokens` y `detail`; 02/03 lo exponen como herramienta que promete `answer`, `citations [{url,title}]`, `grounded`), que no se tocan. Añadir campos es compatible hacia atrás: un cliente que ignora claves desconocidas sigue funcionando igual, y uno nuevo puede distinguir *por qué* no hubo respuesta (fuera de dominio frente a contexto insuficiente), cosa que `grounded=false` sola no dice. Un "no sé" es una respuesta válida, no un error: va con 200, como antes iba `grounded=false`. Un endpoint aparte duplicaría el camino de respuesta y los clientes existentes no ganarían el clasificador ni el umbral. `reason` viaja como `null` (no se omite) para que el campo exista siempre y se pueda comparar sin mirar si está.
- **Revisar si:** algún cliente valida el esquema estrictamente (sin admitir claves extra), o si se agregan rutas nuevas al grafo (entonces, ampliar los valores de `route`/`reason` y documentarlos aquí).

### D34. LangSmith vs Langfuse para el tracing
- **Elegido:** LangSmith, **opcional** y apagado por defecto (`LANGSMITH_TRACING=false`, `LANGSMITH_API_KEY=`, `LANGSMITH_PROJECT=docs-agent`). `pydantic-settings` lee `.env` pero LangSmith solo mira `os.environ`, así que `configure_tracing` (`src/docs_agent/tracing.py`) copia esas tres variables a `os.environ` solo si `LANGSMITH_TRACING=true` **y** hay key, y devuelve si quedó activo. La API la llama una vez al arrancar (`lifespan`); si devolvió `True` importa `wrap_openai` ahí mismo, una sola vez (no en cada petición), y envuelve con él el cliente OpenAI de cada petición, y el clasificador y la respuesta aparecen como corridas LLM hijas con sus tokens (con eso LangSmith estima el costo). La corrida del grafo se llama `ask` y lleva la pregunta en `metadata` (`ainvoke(..., config={"run_name": "ask", "metadata": {"question": ...}})`); la ruta solo se conoce al terminar, así que `route`/`reason` quedan en las outputs de la corrida (el estado final), no en su metadata. El servidor MCP también llama a `configure_tracing` al arrancar (lanzado por la API hereda `os.environ`, y con él las LANGSMITH_*) y sus herramientas llevan `@traceable(run_type="tool")`. `LANGSMITH_API_KEY` es `SecretStr`, como `OPENAI_API_KEY`: no sale en el `repr` de `Settings`.
- **Datos que salen:** con el tracing activo, las preguntas, las respuestas, los fragmentos recuperados y los prompts se envían a LangSmith (servicio externo). En este proyecto son datos públicos (la documentación de FastAPI y preguntas de demo); con datos privados habría que revisarlo antes de activarlo.
- **Ruido silenciado:** `wrap_openai` serializa con `model_dump()` la respuesta de `chat.completions.parse` y pydantic emite en cada llamada estructurada un `UserWarning` (`PydanticSerializationUnexpectedValue(Expected `none` ... field_name='parsed')`) porque el `ParsedChatCompletion` del SDK de OpenAI tipa `parsed` con un TypeVar de default `None`; el valor trazado es correcto. `wrap_openai` no tiene opción para evitarlo, así que al arrancar con tracing se instala un filtro de proceso acotado por mensaje exacto, categoría `UserWarning` y módulo `pydantic.main` (`tracing.install_tracing_warning_filters`); cualquier otro warning sigue saliendo.
- **Key usada:** un Personal Access Token con vencimiento a 90 días. **Mejora de mínimo privilegio:** una key "Tracing Only" (solo escritura de trazas), que no permite leer proyectos ni datasets si se filtra.
- **Límite conocido:** las corridas de herramientas del servidor MCP aparecen como **trazas raíz separadas**, no anidadas bajo la traza `ask` del grafo: el contexto de la traza no viaja por stdio (no hay propagación distribuida entre la API y el subproceso). Se correlacionan por hora y por los argumentos (la pregunta va como `query` de `search_docs`). **Mejora posible:** mandar las cabeceras de traza de LangSmith (`RunTree.to_headers()`) como argumento o `_meta` de la llamada MCP y que el servidor las use como padre (`tracing_context(parent=...)`).
- **Alternativas:** Langfuse (open source, autoalojable o en su nube); OpenTelemetry con un backend genérico; solo logs (`[mcp] ...` y `token_usage`) sin tracing.
- **Por qué:** LangGraph se integra **de forma nativa** con LangSmith: con las variables de entorno cada nodo del grafo ya es un paso de la traza, sin callbacks ni código extra, y `wrap_openai`/`@traceable` cubren lo que no pasa por LangChain. El plan gratis **Developer** alcanza de sobra para un proyecto de portafolio. Langfuse haría lo mismo con un callback handler y es la opción si hiciera falta autoalojar los datos, pero aquí sería una pieza más (cuenta o contenedor) sin ganar nada que se use. Que sea **opcional** es la condición: apagado no cambia nada (`configure_tracing` no toca `os.environ`, el cliente OpenAI no se envuelve y ni siquiera se importa `langsmith.wrappers`), los tests lo fuerzan apagado y ninguno habla con LangSmith.
- **Revisar si:** los datos de las trazas no pueden salir de la infraestructura propia (entonces, Langfuse autoalojado), o si las trazas separadas de las herramientas estorban al depurar (entonces, la propagación de contexto de arriba).

### D35. La política de grounding va en el cliente, no en el servidor MCP
- **Elegido:** una instrucción **del lado del cliente**: `demo/CLAUDE.md` para Claude Code (la carpeta `demo/` trae también `.mcp.json` con el servidor en scope de proyecto) y el mismo texto como instrucciones de Proyecto en Claude Desktop. Dice: para cualquier pregunta técnica, consulta primero `docs-agent` y responde solo con lo que devuelva; si `in_corpus=false` o los resultados solo mencionan el tema, dilo y no completes con conocimiento general. Las `instructions` del servidor quedan como estaban (D27/D28).
- **Alternativas:** endurecer las `instructions` del servidor ("para cualquier pregunta técnica llama primero a `search_docs`"); hacer las dos cosas; no hacer nada y aceptar que Claude responda de memoria lo que no es FastAPI.
- **Por qué:** un servidor MCP **ofrece** herramientas, no puede **forzar** que el cliente las use. Sus `instructions` son contexto que el cliente puede ponderar, y en el ensayo no bastaron: sin la instrucción del cliente, Claude decidió que la pregunta de Django REST Framework "no es de FastAPI", **no llamó a ninguna herramienta** y explicó los permisos de DRF de memoria (justo lo que el momento 3 de la demo prohíbe). Con la instrucción en el cliente, la misma pregunta hizo `search_docs` → `in_corpus=false` → "la documentación indexada no cubre esto" y ofreció lo que sí está (OAuth2 scopes). Cuándo consultar y qué fuentes aceptar es **política de grounding**, y esa política es del cliente, igual que el razonamiento (D27: el servidor da herramientas de bajo nivel y el cliente decide). Endurecer el servidor sería que dicte conducta fuera de su dominio a todo cliente que lo conecte, y Claude ya había pasado por alto el "Answer ONLY..." que tiene.
- **Revisar si:** la política tiene que valer en clientes que no controlamos (entonces la única garantía es no exponer herramientas sino una respuesta ya aterrizada, como el MCP de n8n o `/ask`).
