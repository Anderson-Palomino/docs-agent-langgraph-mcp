# Notas de la integración n8n

Decisiones del ejercicio (formato: Elegido / Alternativas / Por qué) y lo que fui aprendiendo.

## N1. Versión de n8n fijada

- **Elegido:** imagen `n8nio/n8n:2.46.4`.
- **Alternativas:** `latest`, `stable`, o la 3.x.
- **Por qué:** al 2026-11-03, GitHub marca la 2.46.4 como *Latest* y la 3.0/3.1 como *pre-release*; además, la 3.0 trae cambios incompatibles. Fijar la versión permite verificar cada nodo contra la doc de **esa** versión, y evita que un `docker pull` cambie la interfaz a mitad del ejercicio.

## N2. Cómo se ven n8n y docs-agent

- **Elegido:** el compose de n8n se une como **red externa** a `docs-agent-langgraph-mcp_default`, la red por defecto del compose de docs-agent. Desde n8n se usa `http://api:8000` y `db:5432`.
- **Alternativas:** `host.docker.internal:8000`, que sale al host y vuelve a entrar por el puerto publicado; o un único compose con todo.
- **Por qué:** con la red compartida, n8n habla con los servicios por nombre, como lo haría en un servidor on-premise real, y no depende del puerto que el host publique. Un solo compose mezclaría dos proyectos que se levantan por separado. Costo: hay que levantar docs-agent **antes** que n8n; si no, falla con "network not found".

## N3. Base de datos propia de n8n

- **Elegido:** el SQLite que trae n8n por defecto, dentro del volumen `n8n_data`.
- **Alternativas:** usar Postgres como base de n8n (`DB_TYPE=postgresdb`).
- **Por qué:** en un ejercicio de una sola instancia, SQLite basta y es una pieza menos. En producción, o en modo *queue* con varios workers, se usa Postgres. Ojo: la tabla de log del Paso 2 **sí** va en el Postgres de docs-agent; eso es un dato de negocio, no la base interna de n8n.

## N4. Puerto solo en loopback

- **Elegido:** `127.0.0.1:5678:5678`.
- **Alternativas:** `5678:5678`, que publica en todas las interfaces.
- **Por qué:** n8n guarda credenciales y ejecuta código; no debe quedar expuesto a la LAN. Para acceso remoto real se pone un proxy inverso con TLS delante.

## Avisos que muestra n8n al arrancar

- Sale una deprecación del modo *internal* de los *task runners* (que ejecutan el nodo Code) y de algunos valores por defecto que bajarán en versiones futuras. No usamos el nodo Code, así que no se configura nada; queda anotado por si pregunta "¿cómo escalarías n8n?": los *task runners* se ejecutan como proceso aparte (modo `external`).

## N5. Dónde se crea la tabla de log

- **Elegido:** un SQL propio e idempotente (`sql/001_n8n_question_log.sql`, con `CREATE TABLE IF NOT EXISTS`) que se aplica a mano con `psql` dentro del contenedor `db`.
- **Alternativas:** agregar la tabla a `db/init.sql` de docs-agent, o crearla desde n8n con un nodo Postgres de "ejecutar query".
- **Por qué:** `db/init.sql` solo corre cuando el volumen de Postgres es nuevo, así que en una base existente no haría nada, y además mezclaría la integración con el núcleo de docs-agent. Crearla desde un workflow esconde el esquema dentro de n8n. Con un archivo versionado, el esquema queda a la vista en git.
- **Columnas de tokens separadas + `total_tokens`:** el total permite sumar el consumo del día con un `SELECT` simple (es el extra de "cortar si pasa N tokens"); por eso hay un índice en `created_at`. `http_status` es obligatorio porque también se registran las llamadas fallidas: el monitoreo tiene que ver los errores, no solo los éxitos.

## N6. Errores de la API: "Never Error" + IF por status, no Error Trigger

- **Elegido:** el HTTP Request a `/ask` tiene **Never Error** e **Include Response Headers and Status** activados. Después, un IF (`¿/ask respondió 200?`) decide el camino.
- **Alternativas:** dejar que el nodo falle y capturar el fallo con un workflow de **Error Trigger**, o activar *Retry On Fail* en el nodo.
- **Por qué:** con un webhook esperando respuesta, si el nodo revienta, el cliente recibe un 500 genérico. Así, un 422 (pregunta inválida), un 429 (presupuesto agotado) o un 503 (corpus vacío) se devuelven al cliente **con su mismo código** y el `detail` de docs-agent. El Error Trigger sirve para avisar (Slack, correo) cuando algo falla en un workflow **sin** cliente esperando. *Retry* no ayuda con un 422 y docs-agent ya reintenta contra OpenAI.
- **Aprendido:** la salida del HTTP Request con "Include Response Headers and Status" tiene la forma `{ body, headers, statusCode, statusMessage }`; por eso los nodos siguientes usan `$json.statusCode` y `$json.body.answer`.

## N7. Se registran también las llamadas fallidas

- **Elegido:** las tres ramas (con respaldo, sin respaldo, error de `/ask`) terminan en el mismo nodo Postgres. Las fallidas guardan `question` + `http_status` y dejan el resto en null.
- **Alternativas:** registrar solo los éxitos.
- **Por qué:** monitorear un agente en producción es ver también la tasa de errores y de "no encontré", no solo el consumo de tokens. Con este log sale directo: `select http_status, grounded, count(*), sum(total_tokens) from n8n_question_log group by 1, 2`.
- **Detalle:** el nodo Postgres usa **Map Automatically**: cada campo del item va a la columna con el mismo nombre. Por eso los nodos **Edit Fields (Set)** arman items con exactamente los nombres de las columnas. `citations` se manda como texto JSON y Postgres lo guarda como `jsonb` (verificado: `jsonb_typeof = array`).

## N8. Un solo "Responder" con status dinámico + un "Responder 400" temprano

- **Elegido:** si falta `question`, se responde 400 **antes** de llamar a la API (no se gasta nada). Si no, un único Respond to Webhook al final usa `{{ $json.http_status }}` como código y arma el body según el caso.
- **Alternativas:** un Respond to Webhook por rama.
- **Por qué:** con un solo nodo final, todas las respuestas pasan primero por el log. El Webhook está en modo **"Using 'Respond to Webhook' Node"** justamente para controlar código y cuerpo.
- **Aprendido:** la URL de prueba (`/webhook-test/ask`) solo funciona mientras el editor está "escuchando"; la de producción (`/webhook/ask`) solo después de **Publish**. En la 2.x, "publicar" reemplaza al antiguo interruptor "Active", y cada publicación crea una versión con nombre.

## Exportar sin secretos

`n8n export:workflow` nunca incluye el valor de las credenciales: solo `{id, name}`. Pero **sí** incluye al dueño (nombre y correo) en `shared`. `sanitize_export.py` quita eso y los metadatos de la instancia, y falla si queda algún `@`. El export limpio se volvió a importar sin errores (`n8n import:workflow`).

## N9. Cómo recibe la herramienta MCP sus argumentos

- **Elegido:** un **HTTP Request** usado como herramienta (en el JSON se llama `httpRequestTool`), colgado del **MCP Server Trigger**. El body usa `$fromAI('question', 'La pregunta sobre FastAPI…', 'string')`.
- **Alternativas:** **Call n8n Workflow Tool** apuntando a un sub-workflow con **Execute Workflow Trigger** que declara el input `question`.
- **Por qué:** la doc de `$fromAI` solo lo menciona para herramientas de un AI Agent, así que había que probarlo. Funcionó: n8n convierte cada `$fromAI` en un parámetro del esquema de la herramienta que ve el cliente MCP (`tools/list` muestra `question: string`). El sub-workflow quedaría para lógica más larga (validar, registrar en el log, etc.).
- **Detalle:** el nombre del nodo (`ask_docs_agent`) es el nombre de la herramienta, y su **Description** es lo que lee el modelo para decidir cuándo usarla. Esa descripción es, en la práctica, parte del prompt.

## N10. MCP sin agente de n8n, protegido con Bearer

- **Elegido:** el workflow expone `/ask` directamente como herramienta MCP. **Claude Code hace de agente**: él decide cuándo llamar a la herramienta. Autenticación: **Bearer Auth** con un token aleatorio de 32 bytes.
- **Alternativas:** exponer un AI Agent de n8n (dos LLM en cadena, más costo y más latencia); autenticación **None**; o **n8n User Auth (OAuth2)**.
- **Por qué:** MCP sirve para que *cualquier* cliente (Claude Code, Claude Desktop, Copilot…) use herramientas internas sin integrarlas una por una. Si el cliente ya es un agente, poner otro agente detrás solo duplica decisiones. Con **None**, cualquiera que llegue al puerto puede usar la herramienta (y gastar tokens de OpenAI). OAuth2 conviene cuando cada usuario debe entrar con su propia cuenta de n8n.
- **Dónde vive el token:** en `integrations/n8n/.env` (ignorado), en la credencial de n8n y en la config **local** de Claude Code (`~/.claude.json`, registrado con `claude mcp add --scope local`). Nunca en el repo: lo comprueba un `grep` del valor exacto antes de commitear.
- **Aprendido:** en el nodo v2 la URL es `/mcp/<path>` (producción) o `/mcp-test/<path>` (prueba) y el transporte es HTTP con *streaming*, sin las rutas `/sse` del v1. El servidor responde a `initialize`, `tools/list` y `tools/call` como cualquier servidor MCP (`smoke_mcp.py` lo prueba "a mano", sin SDK).

## N11. Key de OpenAI propia para n8n, con permisos mínimos

- **Elegido:** una key nueva (`n8n-ejercicio`) en el mismo proyecto de OpenAI, **Restricted** con solo dos permisos: **List models: Read** y **Chat completions: Write**. Caduca en 7 días. Va directo a la credencial de n8n con `import-openai-credential.ps1`, que la lee del portapapeles, la pasa por stdin al contenedor (n8n la cifra al importar) y vacía el portapapeles.
- **Alternativas:** reutilizar la key de docs-agent; darle permisos "All".
- **Por qué:** con keys separadas, el consumo de cada servicio se ve por separado en el panel de OpenAI, y se puede revocar una sin romper la otra. Los permisos mínimos limitan el daño si la key se filtra. El tope mensual del proyecto sigue cubriendo ambas.
- **Por qué esos dos permisos:** el nodo OpenAI Chat Model carga la lista de modelos con `GET /v1/models` (sin ese permiso, el desplegable falla) y luego llama a `/v1/chat/completions`.
- **Ojo (la doc y el código no coinciden):** docs.n8n.io dice que *Use Responses API* viene apagado, pero en el nodo **v1.3** de n8n 2.46.4 el valor por defecto es **`true`** (lo vi en el código del nodo). Con esta key, que no tiene `/v1/responses`, habría fallado. Quedó en `false` explícito en el workflow. Lección: verificar contra la versión instalada, no solo contra la doc.

## N12. Workflow fijo vs. agente: lo que se vio en este ejercicio

- **`01-ask-log` (workflow fijo):** el camino lo deciden los IF. Siempre se llama a `/ask` una vez. Es predecible, barato y fácil de auditar; sirve cuando el proceso se conoce de antemano.
- **`03-agente-docs` (AI Agent):** el **modelo** decide si usa la herramienta. Medido en el chat de n8n:
  - pregunta de FastAPI: modelo → `ask_docs_agent` → modelo (2 llamadas al LLM + 1 a la herramienta), **646 tokens** de n8n, más los de docs-agent;
  - "hola": 1 llamada al LLM y ninguna herramienta, **217 tokens**.
- **Costo de la flexibilidad:** cada respuesta con herramienta paga el LLM dos veces, más el RAG de docs-agent por dentro. Y el comportamiento depende del prompt de sistema y de la **descripción de la herramienta**, que el modelo lee para decidir.
- **Sin memoria:** el agente no tiene nodo Memory, así que cada mensaje es independiente. Para una conversación de varios turnos se agrega *Simple Memory* (o Postgres Chat Memory en producción).
- **Control de consumo de un agente en producción:** límite de iteraciones del agente, modelo chico por defecto, tope de tokens por día (como el `ASK_DAILY_TOKEN_BUDGET` de docs-agent o el extra de "cortar si pasa N" sobre `n8n_question_log`), keys separadas con presupuesto propio, y registrar los tokens de cada ejecución.

### Prompt de sistema del agente

```
Eres un asistente técnico de FastAPI. Respondes en español, breve y concreto.
- Para cualquier pregunta sobre FastAPI, usa SIEMPRE la herramienta ask_docs_agent; no respondas de memoria.
- Cita las URLs que devuelva la herramienta, tal cual.
- Si la herramienta devuelve grounded: false, di que la documentación no cubre eso; no inventes.
- Saludos o charla general: responde tú, sin usar la herramienta.
```

Cada línea tiene un fin: "SIEMPRE … no respondas de memoria" evita que el modelo conteste con lo que sabe de entrenamiento, sin citas; "tal cual" evita URLs inventadas; la regla de `grounded: false` traslada al agente la señal anti-alucinación de docs-agent; y la última línea evita gastar una llamada a la herramienta en un saludo.
