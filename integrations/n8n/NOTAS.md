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
