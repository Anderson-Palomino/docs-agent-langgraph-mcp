# n8n + agente de IA + MCP — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (inline, sin subagentes, a pedido de Anderson). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** levantar n8n on-premise junto a docs-agent y construir tres workflows (webhook con log en Postgres, herramienta expuesta por MCP para Claude Code y agente de IA con herramienta), aprendiendo n8n en el camino.

**Architecture:** n8n corre en su propio compose (`integrations/n8n/`) y se une como red externa a la red por defecto del compose de docs-agent, así llama a `http://api:8000/ask` y a `db:5432` por nombre de servicio. Anderson arma los workflows en la UI; Claude explica cada nodo (verificado en docs.n8n.io), revisa y escribe compose, SQL, README y NOTAS. Los workflows se exportan a JSON sin credenciales.

**Tech Stack:** n8n 2.46.4 (`n8nio/n8n:2.46.4`, SQLite propio en volumen), Docker Compose, Postgres 17 + pgvector de docs-agent, OpenAI gpt-4.1-mini, Claude Code como cliente MCP.

**Spec:** `C:\Users\ander\Downloads\N8N_PLAN.md` (no se commitea: nombra al empleador) + decisiones del brainstorming del 2026-11-03 (red compartida, key nueva solo para n8n, Paso 3 en dos capas 3a/3b, versión fijada, SQL propio, MCP con bearer, TZ Lima, no correr pytest).

## Global Constraints

- Rama `feat/n8n-integracion`; todo en `integrations/n8n/` salvo este plan.
- Imagen fijada `n8nio/n8n:2.46.4` (stable/Latest en GitHub al 2026-11-03; 3.x es pre-release). Nada de `latest`.
- Puerto de n8n solo en `127.0.0.1:5678`.
- Ningún secreto en git: credenciales solo dentro de n8n; token MCP solo en n8n y en la config **local** de Claude Code. Antes de cada commit: `grep -rniE "sk-|bearer [a-z0-9]|password|apikey" integrations/n8n/` sin hallazgos reales.
- Repo público: **no nombrar al empleador ni el proceso de selección** en ningún archivo commiteado.
- Antes de usar un nodo: confirmar en docs.n8n.io nombre exacto y campos; si la UI de 2.46.4 difiere de la doc, manda la UI y se anota en NOTAS.
- Cada decisión va a `integrations/n8n/NOTAS.md` (Elegido / Alternativas / Por qué), en español, numeradas N1, N2…
- **No correr `pytest`** durante el ejercicio (los tests de integración vacían la base viva).
- Si un paso pasa de 20 min: parar y proponer atajo.
- Commits con identidad Anderson-Palomino + noreply y trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Corte por tiempo: Paso 1 → Paso 2 completo → 3a → 3b → extras. 3b y extras son recortables.

## Review Focus

1. `/ask` responde 422/429/502/503 (pregunta vacía, presupuesto agotado, OpenAI caído, corpus vacío) → el webhook igual responde, con el código y un mensaje claro; nunca se queda colgado ni devuelve un 500 genérico. *(Task 3, Step 5)*
2. Body sin `question` o que no es JSON → respuesta 400 con mensaje, sin llamar a `/ask`. *(Task 3, Step 5)*
3. Pregunta con comillas, saltos de línea o tildes → llega intacta a `/ask` (body armado como JSON con expresión, no concatenando texto). *(Task 3, Step 5)*
4. JSON exportados → contienen id/nombre de credencial pero ningún valor secreto. *(Tasks 3, 4, 5: paso de exportación)*
5. URL de prueba (`/webhook-test/…`, solo con "Listen") vs URL de producción (`/webhook/…`, solo con el workflow publicado) → las verificaciones con `curl` usan producción con el workflow publicado. *(Task 3, Step 5; Task 4, Step 4)*

---

### Task 0: Preparar el terreno

**Files:** ninguno (más este plan, que se commitea aquí).

- [ ] **Step 1:** `git checkout -b feat/n8n-integracion` desde `main` limpio.
- [ ] **Step 2:** Anderson abre Docker Desktop (recordatorio: también reinicia los contenedores Supabase de MedicionHoras). Verificar con `docker ps`.
- [ ] **Step 3:** `docker compose up -d` en la raíz de docs-agent. Verificar `curl -s http://127.0.0.1:8000/health` → `{"status":"ok","chunks":N}` con N > 0. Si N = 0, correr el ingest según el README de docs-agent antes de seguir.
- [ ] **Step 4:** `docker network ls` → existe `docs-agent-langgraph-mcp_default` (nombre que usará el compose de n8n).
- [ ] **Step 5:** commit del plan: `docs: plan de integración n8n`.

### Task 1: Paso 1 — n8n on-premise en Docker

**Files:**
- Create: `integrations/n8n/docker-compose.yml`
- Create: `integrations/n8n/.env.example`
- Create: `integrations/n8n/NOTAS.md`

**Interfaces:**
- Produces: servicio `n8n` en `http://127.0.0.1:5678`, con acceso por DNS de Docker a `api:8000` y `db:5432`.

- [ ] **Step 1:** escribir `docker-compose.yml`: servicio `n8n`, imagen `n8nio/n8n:2.46.4`, `ports: ["127.0.0.1:5678:5678"]`, volumen nombrado `n8n_data` → `/home/node/.n8n`, `env_file: .env`, `restart: unless-stopped`, redes `default` + `docs_agent` (external, `name: docs-agent-langgraph-mcp_default`).
- [ ] **Step 2:** `.env.example` con `GENERIC_TIMEZONE=America/Lima`, `TZ=America/Lima`, `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true`. Sin secretos (no hay ninguno que poner). Anderson copia a `.env` (ya ignorado por el `.gitignore` raíz: verificar con `git check-ignore integrations/n8n/.env`).
- [ ] **Step 3:** `docker compose up -d` en `integrations/n8n/`. Verificar: `docker compose logs n8n` muestra "Editor is now accessible".
- [ ] **Step 4:** Anderson abre `http://127.0.0.1:5678` y crea el usuario owner. Si la UI se queja de cookie segura, recién ahí añadir `N8N_SECURE_COOKIE=false` y anotarlo.
- [ ] **Step 5:** verificar conectividad: `docker compose exec n8n wget -qO- http://api:8000/health` → JSON con `"status":"ok"`.
- [ ] **Step 6:** `NOTAS.md` con N1 versión fijada, N2 red compartida vs `host.docker.internal`, N3 SQLite propio de n8n vs Postgres, N4 puerto solo en loopback.
- [ ] **Step 7:** escaneo de secretos + commit `feat(n8n): compose on-premise unido a la red de docs-agent`.

### Task 2: Tabla de log

**Files:**
- Create: `integrations/n8n/sql/001_n8n_question_log.sql`

**Interfaces:**
- Produces: tabla `n8n_question_log(id bigserial PK, created_at timestamptz default now(), question text not null, answer text, grounded boolean, citations jsonb, embedding_tokens int, prompt_tokens int, completion_tokens int, total_tokens int, http_status int not null)`.

- [ ] **Step 1:** escribir el SQL con `CREATE TABLE IF NOT EXISTS` (idempotente).
- [ ] **Step 2:** aplicarlo: `docker compose exec -T db psql -U docs -d docs < integrations/n8n/sql/001_n8n_question_log.sql` (desde la raíz de docs-agent).
- [ ] **Step 3:** verificar `\d n8n_question_log` → columnas de arriba.
- [ ] **Step 4:** N5 en NOTAS (SQL propio vs editar `db/init.sql`, que solo corre con volumen nuevo). Commit `feat(n8n): tabla n8n_question_log`.

### Task 3: Paso 2 — Workflow `01-ask-log` (Anderson lo arma)

**Files:**
- Create: `integrations/n8n/workflows/01-ask-log.json` (export)

**Interfaces:**
- Consumes: `POST http://api:8000/ask` con `{"question": str}` → `{answer, citations:[{url,title}], grounded, usage:{embedding_tokens,prompt_tokens,completion_tokens}}`; errores 422/429/502/503 con `{"detail": ...}`.
- Produces: `POST http://127.0.0.1:5678/webhook/ask` con `{"question": str}` → `200 {answer, citations, grounded}` | `400 {error}` | `<status de /ask> {error}`.

Nodos (cada uno: Claude explica y verifica en docs antes de que Anderson lo ponga):
1. **Webhook**: POST, path `ask`, Respond = "Using 'Respond to Webhook' Node".
2. **If** "tiene pregunta": `question` existe y no está vacía → si no, Respond to Webhook 400 `{"error":"Falta question"}`.
3. **HTTP Request**: POST `http://api:8000/ask`, body JSON con expresión `{{ { question: $json.body.question } }}`, timeout 60 s, opciones "Never Error" + "Include Response Headers and Status".
4. **If** "status 200": no → **Postgres** (log con `http_status`, sin respuesta) → Respond to Webhook con el mismo status y `{"error": detail}`.
5. **If** "grounded": false → answer = "No encontré esto en la documentación" (nodo **Edit Fields (Set)**).
6. **Postgres** Insert en `n8n_question_log` (credencial: host `db`, puerto 5432, db/usuario/clave `docs`; vive solo en n8n). `total_tokens` = suma de los tres.
7. **Respond to Webhook** 200 con `{answer, citations, grounded}`.

- [ ] **Step 1:** Anderson arma nodos 1–3 y prueba con "Listen for test event" + `curl` a `/webhook-test/ask`. Claude revisa la salida del HTTP Request.
- [ ] **Step 2:** nodos 4–7; publicar el workflow.
- [ ] **Step 3:** verificación feliz: `curl -s -X POST http://127.0.0.1:5678/webhook/ask -H 'Content-Type: application/json' -d '{"question":"¿Cómo se declara un request body?"}'` → 200, `grounded: true`, `citations` no vacía.
- [ ] **Step 4:** verificación sin respaldo: pregunta fuera de tema (`"¿Cuál es la capital de Francia?"`) → `"No encontré esto en la documentación"`.
- [ ] **Step 5 (Review Focus 1–3, 5):** `-d '{}'` → 400; `-d 'no json'` → 4xx con mensaje; pregunta de 1001 caracteres → status 422 propagado; pregunta con `"comillas"` y `\n` → 200. Todas con la URL de producción.
- [ ] **Step 6:** `docker compose exec db psql -U docs -d docs -c "select id, grounded, total_tokens, http_status from n8n_question_log order by id desc limit 5"` → una fila por cada llamada a `/ask` de los Steps 3–5.
- [ ] **Step 7:** exportar a `workflows/01-ask-log.json`; escaneo de secretos (Review Focus 4); N6–N8 en NOTAS (Never Error vs Error Trigger, log también en errores, Set para el mensaje). Commit `feat(n8n): workflow webhook → docs-agent → log`.

### Task 4: Paso 3a — `/ask` como herramienta MCP para Claude Code

**Files:**
- Create: `integrations/n8n/workflows/02-mcp-docs-agent.json` (export)

**Interfaces:**
- Produces: servidor MCP en `http://127.0.0.1:5678/mcp/docs-agent` (HTTP con streaming; auth Bearer), herramienta `ask_docs_agent(question: string)`.

- [ ] **Step 1:** Claude verifica en la UI/doc cómo recibe argumentos una herramienta colgada del **MCP Server Trigger** (esperado: `$fromAI("question", "Pregunta sobre la documentación de FastAPI", "string")` en el body del **HTTP Request**). Si no funciona, alternativa: **Call n8n Workflow Tool** + sub-workflow con **Execute Workflow Trigger** que declara el input `question`. Anotar cuál (N9).
- [ ] **Step 2:** Anderson arma MCP Server Trigger (path `docs-agent`, Authentication = Bearer, token generado con `openssl rand -hex 32`, guardado solo en la credencial de n8n) + herramienta con nombre y descripción claros. Publicar.
- [ ] **Step 3:** Anderson registra el servidor en scope local: `claude mcp add --transport http --scope local n8n-docs-agent http://127.0.0.1:5678/mcp/docs-agent --header "Authorization: Bearer <token>"` (lo escribe él; el token no pasa por el chat). Verificar `claude mcp list` → `n8n-docs-agent ✓ Connected`.
- [ ] **Step 4:** en una sesión **nueva** de Claude Code: "pregúntale a docs-agent cómo se declara un request body" → se llama `ask_docs_agent` y la respuesta trae citas. Sin el header → 401/403 (probar con `curl`).
- [ ] **Step 5:** exportar, escaneo de secretos (el token no debe aparecer), N10 (MCP sin agente de n8n: Claude Code es el agente; bearer vs ninguna). Commit `feat(n8n): docs-agent expuesto como servidor MCP`.

### Task 5: Paso 3b — Agente de IA en n8n (recortable)

**Files:**
- Create: `integrations/n8n/workflows/03-agente-docs.json` (export)

- [ ] **Step 1:** Anderson crea la key nueva en su org de OpenAI, restringida (permisos de modelos: lectura; chat completions: escritura), y la carga **solo** como credencial OpenAI en n8n. Si la prueba de credencial falla, abrir solo el permiso que falte y anotarlo (N11).
- [ ] **Step 2:** workflow: **Chat Trigger** → **AI Agent** (system message escrito por Anderson) + sub-nodos **OpenAI Chat Model** (`gpt-4.1-mini`, Use Responses API desactivado) y **HTTP Request** como herramienta hacia `/ask` con `$fromAI`.
- [ ] **Step 3:** verificar en el chat de n8n: pregunta de FastAPI → el log de ejecución muestra la llamada a la herramienta y la respuesta cita URLs; "hola" → responde sin llamar a la herramienta.
- [ ] **Step 4:** exportar, escaneo, N12 (workflow fijo vs agente; cuándo cada uno). Commit `feat(n8n): agente de IA con docs-agent como herramienta`.

### Task 6: README, NOTAS y cierre

**Files:**
- Create: `integrations/n8n/README.md`
- Create: `integrations/n8n/img/*.png` (capturas que toma Anderson)
- Modify: `integrations/n8n/NOTAS.md`

- [ ] **Step 1:** README: requisitos, orden de arranque (docs-agent primero: la red externa debe existir), `.env`, aplicar el SQL, importar workflows y crear credenciales a mano, `curl` de ejemplo, conectar Claude Code, una captura por workflow.
- [ ] **Step 2:** NOTAS: sección "Lo que aprendí", en palabras de Anderson.
- [ ] **Step 3:** escaneo final de secretos y de nombres de empleador (`grep -rni` del nombre sobre `integrations/` y este plan) → vacío. Commit `docs(n8n): README y notas`.
- [ ] **Step 4:** superpowers:requesting-code-review sobre la rama, y después superpowers:finishing-a-development-branch.

### Task 7: Ensayo de preguntas

- [ ] **Step 1:** 5 preguntas, una por una, corrigiendo cada respuesta antes de la siguiente (workflow fijo vs agente; errores de API externa; on-premise vs nube; control de tokens; qué es MCP y para qué sirvió). Lo que salga flojo se suma a NOTAS (fuera del repo si nombra al empleador).

### Extras (solo si sobra tiempo)

- Slack o correo con la respuesta.
- Corte por consumo: antes del HTTP Request, Postgres `select coalesce(sum(total_tokens),0) from n8n_question_log where created_at >= date_trunc('day', now() at time zone 'America/Lima')` → si pasa N, responder 429.
