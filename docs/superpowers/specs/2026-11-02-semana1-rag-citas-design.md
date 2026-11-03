# Semana 1 — RAG con citas sobre la doc de FastAPI (diseño)

Fecha: 2026-11-02 · Autor: Anderson Palomino (con Claude Code)
Plan madre: `PLAN.md` (raíz del repo).

## 1. Intención y por qué

Proyecto de portafolio para postular a roles de AI Engineer. La Semana 1 deja la base
sobre la que se apoyan las semanas 2–4: un endpoint `/ask` que responde preguntas sobre
la documentación pública de FastAPI **citando la URL de origen**, levantable con
`docker compose up`. Todavía **sin agente** (LangGraph llega en la Semana 2).

Anderson va a estudiar este código para explicarlo en entrevistas. Por eso el RAG se
escribe de forma explícita y legible, sin frameworks que escondan los pasos, y cada
decisión técnica importante queda en `docs/decisiones.md` (qué se eligió, alternativas,
por qué).

## 2. Metas

- `docker compose up` levanta Postgres+pgvector y la API FastAPI.
- Un comando de ingesta descarga la doc de FastAPI (inglés, versión fijada), la divide en
  fragmentos, genera embeddings y los guarda en pgvector.
- `POST /ask` recupera los 5 fragmentos más cercanos y responde con
  `{answer, citations[]}`; cada cita es una URL pública de `fastapi.tiangolo.com`
  (con ancla de sección) que pertenece a los fragmentos recuperados.
- El asistente responde en el idioma de la pregunta (español o inglés).
- Límite de gasto de tokens configurable por variable de entorno.
- Tests con pytest en cada paso; commits pequeños.
- 5 preguntas de ejemplo (al menos 1 en español) respondidas con cita, documentadas en
  el README.
- `docs/decisiones.md` con cada decisión importante.

## 3. No-metas (Semana 1)

- Nada de LangGraph, agente, clasificación de preguntas ni rama "no sé" (Semana 2).
- Nada de servidor MCP (Semana 2).
- Nada de golden set de 30 preguntas, evaluación automatizada ni trazas (Semana 3).
- Nada de despliegue (Semana 3). README final en inglés pulido (Semana 4); en S1 basta un
  README funcional en inglés.
- Sin frontend, sin autenticación, sin streaming.
- Sin re-ranking, búsqueda híbrida ni re-ingesta incremental.

## 4. Anti-metas (sería un fracaso aunque funcione)

- Citas inventadas: una URL en `citations` que no venga de los fragmentos recuperados.
- Usar cualquier dato que no sea público (nada de BaldeCash, GENIA ni clientes).
- Que un revisor no pueda levantarlo con `docker compose up` + ingesta siguiendo el README.
- Código "mágico" que Anderson no pueda explicar línea a línea (p. ej. un
  `RetrievalQA` de LangChain que oculte el prompt y la consulta).
- Gasto de tokens sin tope.
- Secretos (OPENAI_API_KEY) commiteados.

## 5. Restricciones

- Stack fijado por `PLAN.md`: Python, FastAPI, PostgreSQL + pgvector, OpenAI
  `gpt-4.1-mini` + `text-embedding-3-small`, Docker Compose, pytest.
- Presupuesto de tiempo: ~4 h de construcción esta semana.
- Entorno de Anderson: Windows 11, Docker Desktop, Python 3.13 local, Git, `gh` con
  cuenta `Anderson-Palomino`. `uv` no está instalado aún.
- Repo: `C:\dev\docs-agent-langgraph-mcp`, se publica como
  `github.com/Anderson-Palomino/docs-agent-langgraph-mcp` (público) **solo tras
  confirmación de Anderson** al cerrar la rama.

## 6. Decisiones tomadas (aprobadas en el brainstorming)

| Tema | Decisión | Origen |
| --- | --- | --- |
| Corpus | Doc de FastAPI en inglés, Markdown de `fastapi/fastapi` → `docs/en/docs/`, fijada a un tag de release | Recomendación de Claude, aprobada |
| Idioma | Responde en el idioma de la pregunta; doc, README y ejemplos en inglés | Recomendación de Claude, aprobada |
| Gestor de deps | Python 3.12 + `uv` | Claude, aprobada |
| Chunking | Por encabezados Markdown (`##`/`###`), con tope de tamaño y solapamiento; cita = URL + `#ancla` | Claude, aprobada |
| Esquema DB | Tabla con `vector(1536)` + índice HNSW coseno, creada por script SQL de init (sin Alembic) | Claude, aprobada |
| Librerías | SDK de OpenAI + psycopg directo; **sin LangChain en S1** | Claude, aprobada |
| Respuesta | Salida estructurada `{answer, citations[]}`; validar que cada cita ∈ fragmentos recuperados | Claude, aprobada |
| Ingesta | Comando aparte (no corre en `up`) | Claude, aprobada |
| Tests | pytest; OpenAI mockeado en unitarios; integración contra Postgres real | Claude, aprobada |
| Publicación | Repo público solo tras confirmar al cerrar la rama | Claude, aprobada |

### 6.1 Respuestas de Anderson tras el builder check

- **OpenAI real:** Anderson pone su `OPENAI_API_KEY` en `.env` (en `.gitignore`, nunca
  en el chat). Claude corre la ingesta real y el smoke test con las 5 preguntas, y pega
  las salidas reales en el README. Costo esperado: menos de 1 USD.
- **Identidad git (solo en este repo):** `Anderson-Palomino`
  `<170631001+Anderson-Palomino@users.noreply.github.com>`. No se usa el correo de
  BaldeCash.
- **Trailer:** los commits llevan `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 7. Diseño

### 7.1 Estructura propuesta

```
docs-agent-langgraph-mcp/
  PLAN.md
  README.md
  docker-compose.yml
  Dockerfile
  pyproject.toml / uv.lock
  .env.example            # OPENAI_API_KEY, DATABASE_URL, límites de tokens, FASTAPI_DOCS_REF
  db/init.sql             # extensión vector + tablas + índice
  src/docs_agent/
    config.py             # settings desde env (pydantic-settings)
    db.py                 # conexión psycopg + registro de pgvector
    ingest/
      fetch.py            # descarga Markdown del tag fijado
      chunk.py            # división por encabezados → fragmentos con url+ancla
      embed.py            # embeddings por lotes
      run.py              # CLI: python -m docs_agent.ingest.run
    rag/
      retrieve.py         # top-k por distancia coseno
      answer.py           # prompt + salida estructurada + validación de citas
    budget.py             # contador/tope de tokens
    api.py                # FastAPI: POST /ask, GET /health
  tests/
  docs/decisiones.md
  docs/superpowers/specs/, docs/superpowers/plans/
```

La estructura es orientativa; el builder puede ajustarla si lo justifica en decisiones.md.

### 7.2 Ingesta

1. **Fetch:** descargar los `.md` de `docs/en/docs/` del tag indicado en
   `FASTAPI_DOCS_REF` (tarball de GitHub o sparse checkout — a criterio del builder).
   Excluir páginas sin valor para Q&A (p. ej. release notes, páginas de traducción/
   patrocinadores) — lista de exclusión explícita y anotada.
2. **URL:** mapear ruta de archivo → URL pública
   (`docs/en/docs/tutorial/body.md` → `https://fastapi.tiangolo.com/tutorial/body/`,
   `index.md` → raíz de su carpeta). Ancla = slug del encabezado, comprobando contra
   2–3 URLs reales que el slug coincide con el que genera MkDocs.
3. **Chunk:** partir por `##`/`###`; si una sección supera el tope (~800 tokens orientativo)
   se subdivide con solapamiento. Cada fragmento guarda: `url`, `title` (título de
   página + encabezado), `content`, `token_count`. Los bloques de código se conservan
   enteros dentro del fragmento cuando sea posible. Los includes de MkDocs
   (`{* ../../docs_src/... *}`) se dejan como texto o se resuelven — decisión del
   builder, anotada.
4. **Embed:** `text-embedding-3-small` por lotes; respeta el tope de ingesta.
5. **Store:** idempotente — re-ejecutar la ingesta reemplaza el corpus del mismo ref
   (p. ej. borrar e insertar en una transacción).

### 7.3 Esquema

- `chunks(id, source_ref, url, title, content, token_count, embedding vector(1536), created_at)`
- índice HNSW `vector_cosine_ops` sobre `embedding`.
- `token_usage(day date, kind text, tokens int)` (o equivalente) para el presupuesto.

### 7.4 `/ask`

- Request: `{"question": str}` (validar longitud máx.).
- Flujo: chequear presupuesto → embeber pregunta → top-5 por coseno → prompt con los
  fragmentos numerados (url + contenido) → `gpt-4.1-mini` con salida estructurada
  (`answer`, `citations: [url]`) → descartar citas que no estén entre los recuperados →
  registrar tokens usados → responder.
- Response: `{"answer": str, "citations": [{"url", "title"}], "usage": {...}}`.
  Incluir los fragmentos recuperados con su distancia es útil para depurar (opcional,
  p. ej. con `?debug=true`).
- El prompt instruye responder solo con el contexto y en el idioma de la pregunta. (La
  rama formal de "no sé" es Semana 2; en S1 el prompt puede decirlo, pero no se mide.)
- **Si la validación descarta todas las citas** *(decisión de Claude tras el builder
  check)*: sin reintento; se devuelve HTTP 200 con la respuesta del modelo,
  `citations: []` y `grounded: false` (cuando hay ≥1 cita válida, `grounded: true`).
  Así no se inventa nada, el cliente sabe que la respuesta no tiene respaldo, y la
  decisión de qué hacer con eso (rama "no sé") queda para el grafo de la Semana 2.

### 7.5 Presupuesto de tokens

- `ASK_DAILY_TOKEN_BUDGET` (tokens por día UTC, sumando embeddings + chat de `/ask`).
  Al superarlo, `/ask` responde HTTP 429 con mensaje claro.
- `INGEST_MAX_TOKENS` (tope por ejecución de ingesta; aborta antes de pasarse,
  estimando con `tiktoken`).
- Contabilidad persistida en Postgres para que sobreviva reinicios y sirva en
  despliegue (Semana 3). Valores por defecto razonables en `.env.example`.

### 7.6 Docker Compose

- Servicio `db`: imagen `pgvector/pgvector` (Postgres 16 o 17), volumen persistente,
  `db/init.sql` montado en `docker-entrypoint-initdb.d`, healthcheck.
- Servicio `api`: build del Dockerfile (Python 3.12 slim + uv), depende de `db` sano,
  puerto 8000, lee `.env`.
- Ingesta: `docker compose run --rm api python -m docs_agent.ingest.run` (o un
  servicio con profile). Documentado en el README.

### 7.7 Tests

- Unitarios: mapeo ruta→URL y slugs de anclas, chunking (encabezados, tope, código),
  validación de citas, presupuesto (429 al exceder), endpoint `/ask` con OpenAI y
  retrieval mockeados.
- Integración (marcados, requieren Postgres de compose): insertar fragmentos con
  embeddings falsos y verificar el orden de top-k.
- Ningún test llama a la API real de OpenAI.
- **Dónde corren** *(decisión de Claude tras el builder check)*: se instala `uv` en el
  host (instalador oficial, a nivel de usuario) y uv gestiona su propio Python 3.12, sin
  tocar el 3.13 del sistema. Los tests unitarios corren en el host con
  `uv run pytest`; los de integración usan el Postgres de compose expuesto en
  `localhost:5432` (puerto de host final: 5434, ver D13) y se saltan si no está disponible (marker `integration`).
- Smoke manual final: ingesta real + 5 preguntas de ejemplo.

### 7.8 docs/decisiones.md

Una entrada por decisión: **Decisión · Alternativas · Por qué · (Cuándo revisarla)**.
Arranca con las de la tabla de la sección 6 y se completa durante la ejecución.

## 8. Criterio de "hecho"

- `docker compose up` + comando de ingesta funcionan desde cero siguiendo el README.
- 5 preguntas de ejemplo (≥1 en español) con respuesta y cita válida, pegadas en el
  README.
- `pytest` en verde.
- `docs/decisiones.md` actualizado.
- Code review hecho y rama cerrada (merge a `main`; publicación en GitHub solo con
  confirmación).

## 9. Queda a criterio del builder

Versión exacta del tag de FastAPI (la última release estable al momento de construir),
método de descarga, tamaño exacto de fragmento y solapamiento, texto del prompt,
parámetros HNSW, valores por defecto de los límites, versión exacta de Postgres/pgvector.
Cada uno queda anotado en `docs/decisiones.md`.
