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
  recall por defecto. Uso coseno porque los embeddings de OpenAI vienen normalizados.
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
  Postgres de otro proyecto local (genia-geo) que ya ocupa el 5433.

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
- **Elegido:** cada sección `##`/`###` (fuera de bloques de código, con fences de ``` o ```` y posible sangría) es un fragmento con su propia URL `#ancla`; la intro antes del primer `##` usa la URL de la página. Si una sección pasa de 800 tokens (cl100k_base) se parte por párrafos acumulando hasta 800, y cada sub-fragmento arranca con las últimas ~100 tokens del anterior (recortadas a límite de palabra). Un párrafo o bloque de código mayor que el tope se deja entero. Corpus real: 147 páginas -> 1088 fragmentos, mediana 129 tokens, máximo 1130 (solo 5 fragmentos > 800, todos bloques de código/párrafos indivisibles); 0 fragmentos cuyo encabezado venga de dentro de un bloque de código.
- **Alternativas:** trocear por tamaño fijo ignorando la estructura; partir también los bloques de código; trocear solo por `##`.
- **Por qué:** cada fragmento corresponde a una sección con ancla propia, así la cita enlaza justo a donde está la respuesta. 800 tokens cabe holgado en el embedding y en el contexto del LLM sin mezclar temas; el solape de 100 evita perder frases en el corte. Partir código lo vuelve inútil, por eso se tolera superar el tope.
