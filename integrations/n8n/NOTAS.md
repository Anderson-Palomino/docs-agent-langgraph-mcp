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
