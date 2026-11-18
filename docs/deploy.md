# Guía de despliegue (Render + Neon)

Por qué estos proveedores y qué se comparó: **D37** en `docs/decisiones.md`. Esta guía no contiene valores secretos: cada variable dice su nombre y de dónde sale el valor. Nunca pegues una clave ni una `DATABASE_URL` en un archivo del repo ni en un commit.

Resumen: base Postgres con pgvector en Neon, API en Render desde el `Dockerfile`, ingesta única desde tu máquina. El servidor MCP no se despliega: dentro del contenedor es un subproceso de la API (stdio). Para Claude Code/Desktop y n8n sigue siendo el servidor local.

## 0. Antes de empezar

- Cuentas: GitHub (el repo debe estar subido para que Render lo lea), Neon, Render y OpenAI (ya la tienes).
- Gasto esperado: la ingesta real midió ~249 000 tokens de embeddings (1 128 fragmentos, 1 070 secciones) con `text-embedding-3-small` (US$0.02 por millón, tarifa de `Settings`) = unos US$0.005. Neon y Render tienen plan gratis; el servicio gratis de Render se duerme a los 15 min y tarda ~1 min en despertar (US$7/mes con Starter para que no se duerma; confirma el precio al crear el servicio).

## 1. Tope de gasto en OpenAI (hazlo primero)

Es la única protección que corta aunque el código falle. Según https://developers.openai.com/api/docs/guides/spend-limits.md :

1. Entra al panel de OpenAI (platform.openai.com) y abre los ajustes del **proyecto** al que pertenece la clave que usarás en producción.
2. Sección **Limits**, bajo **Spend**, edita el límite.
3. Escribe un monto mensual bajo (por ejemplo US$5) y activa **Enforce a hard limit**. Guarda.
4. Al llegar al límite las llamadas de ese proyecto devuelven 429 `project_spend_limit_exceeded`. El corte no es instantáneo: el gasto puede pasarse un poco.
5. Recomendado: crea una clave **solo para producción** dentro de ese proyecto (no reutilices la de tu `.env` local), y un alerta de gasto (solo avisa, no corta; la ruta exacta en el panel no la confirmó la documentación: búscala en los ajustes del proyecto).

## 2. Crear la base en Neon

1. Crea una cuenta en https://neon.com y un proyecto (Postgres reciente; región cercana a la que elegirás en Render, por ejemplo US East si Render va en Ohio/Virginia).
2. En el panel del proyecto, botón **Connect**: copia la cadena de conexión **directa** (el hostname **no** debe contener `-pooler`; si el interruptor "Connection pooling" está activo, apágalo). Déjala tal como la da Neon (conserva los parámetros `sslmode` y `channel_binding`). Esa es tu `DATABASE_URL` de producción. Trátala como secreto: no la pegues en chats ni tickets; si se expone, restablece la contraseña del rol `neondb_owner` en Neon (**Roles**) y actualiza Render.
3. Crea el esquema. En Neon, **SQL Editor**: pega el contenido completo de `db/init.sql` y ejecútalo (empieza con `CREATE EXTENSION IF NOT EXISTS vector;` y crea `chunks`, `sections` y `token_usage`; es idempotente). Alternativa con `psql` instalado: `psql "<DATABASE_URL>" -f db/init.sql`, pero eso deja la URL en el historial de la terminal; prefiere el SQL Editor.
4. Comprueba en el SQL Editor: `SELECT extname FROM pg_extension WHERE extname = 'vector';` debe devolver una fila, y `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';` debe listar las tres tablas. El SQL Editor de Neon no es `psql`: no uses `\dt` ni otros metacomandos.

## 3. Ingesta única desde tu máquina

El comando real es `python -m docs_agent.ingest.run` (ver `src/docs_agent/ingest/run.py`). Descarga la documentación de FastAPI 0.162.0 (`FASTAPI_DOCS_REF`), la parte en fragmentos (147 páginas, 1 128 fragmentos), **calcula los tokens y se aborta antes de llamar a OpenAI si pasan de `INGEST_MAX_TOKENS`** (2 000 000 por defecto; la ingesta real fueron ~249 000), embebe, **reemplaza** el corpus de esa versión y registra el uso. Se puede repetir sin duplicar.

Los comandos de abajo son de PowerShell (en Git Bash `$env:X = ...` no funciona; usa la variante Bash). Ojo: `Read-Host` **muestra en pantalla** el valor que pegas (no queda en el historial ni en archivos). La `DATABASE_URL` de producción se pasa solo por entorno de ese comando, nunca en un archivo. Las variables de entorno tienen prioridad sobre `.env`, así que `OPENAI_API_KEY` se puede seguir leyendo de tu `.env` local (o pásala igual por entorno si quieres usar la clave de producción).

PowerShell:

```powershell
$env:DATABASE_URL = Read-Host "DATABASE_URL de produccion"   # pega la URL de Neon; no queda en el historial
$env:INGEST_MAX_TOKENS = "300000"                            # tope de seguridad por encima de los ~249000 medidos
uv run python -m docs_agent.ingest.run
Remove-Item Env:DATABASE_URL, Env:INGEST_MAX_TOKENS
```

Bash:

```bash
read -rs -p "DATABASE_URL de produccion: " DATABASE_URL && export DATABASE_URL
INGEST_MAX_TOKENS=300000 uv run python -m docs_agent.ingest.run
unset DATABASE_URL
```

Salida esperada: `Ingested <n> chunks from fastapi@0.162.0 (<tokens> tokens)` con n = 1 128 y tokens cercano a 249 000 (lo medido en producción). Verifica en el SQL Editor de Neon: `SELECT count(*) FROM chunks;`, `SELECT count(*) FROM sections;` y `SELECT * FROM token_usage;` (una fila `ingest` con los tokens).

## 4. Crear el servicio en Render

1. Cuenta en https://render.com, conecta tu GitHub y elige el repo. **New > Web Service**.
2. **Language/Runtime: Docker** (usa el `Dockerfile` de la raíz; no hay comando de build ni de inicio que escribir: el `CMD` ya arranca `uvicorn` en el puerto 8000). Región: **Ohio**, para que coincida con Neon us-east-2. Rama: la que quieras desplegar (por ejemplo `main` tras el merge).
3. **Instance type**: el formulario propone por defecto el plan de pago Starter (US$7): **elige Free explícitamente** (se duerme a los 15 min, ~1 min para despertar), o deja Starter (0.5 CPU / 512 MB, no se duerme).
4. **Health Check Path**: `/health`.
5. **Environment variables** (Render las guarda como secretos del servicio; el valor sale de donde dice la columna):

| Variable | Valor / de dónde sale |
|---|---|
| `PORT` | `8000` (no es secreto). Render usa `10000` por defecto y el `Dockerfile` escucha en 8000, así que se declara para que coincidan |
| `OPENAI_API_KEY` | La clave de producción que creaste en el proyecto con tope (paso 1), desde el panel de OpenAI. En **Restricted permissions** concede solo "Chat completions" y "Embeddings" = Request (el código solo llama `client.chat.completions.parse` y `client.embeddings.create`) |
| `DATABASE_URL` | La cadena **directa** de Neon (paso 2), tal como la da Neon (incluye `sslmode` y `channel_binding`) |
| `ASK_DAILY_TOKEN_BUDGET` | Tú lo eliges. Por defecto 200 000 tokens/día (UTC); al agotarse, `/ask` responde 429. No lo subas sin mirar el tope de OpenAI |
| `ASK_RATE_LIMIT_PER_HOUR` | Tú lo eliges. 20 por defecto (por IP, en memoria, por instancia, se reinicia con cada deploy); `0` lo apaga |
| `TRUSTED_PROXY_IPS` | `*`. Detrás de Render todas las peticiones llegan del proxy; con `*` la IP del cliente es la última entrada de `X-Forwarded-For` (D37). Sin esto, todos los visitantes comparten un solo contador |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | Opcionales. Cuenta de LangSmith (clave en Settings > API keys, recomendado "Tracing Only", D34). Déjalas fuera para no enviar trazas |

   Agrégalas **una por una** en Render. El `.env` descargable de Neon trae piezas sueltas (`PGUSER`, `PGPASSWORD`, ...): la app necesita la `DATABASE_URL` única.

   Las demás variables (`CHAT_MODEL`, `TOP_K`, `NO_ANSWER_DISTANCE_THRESHOLD`, etc.) tienen valor por defecto: no hace falta definirlas.
6. **Create Web Service**. El primer build tarda unos minutos (`uv sync`).

## 5. Probar

Con `<URL>` = la dirección `https://<nombre>.onrender.com` que muestra Render (en el plan gratis, la primera petición tras dormir tarda ~1 min):

```bash
curl -s <URL>/health
```

Abre `<URL>/docs` (la página interactiva de FastAPI) y prueba `POST /ask` con una pregunta como `{"question": "How do I declare a query parameter in FastAPI?"}`. Debe responder con citas a la documentación. Revisa también los logs de Render: con el límite activo y `TRUSTED_PROXY_IPS` definida no debe salir el aviso de arranque sobre proxies.

Para comprobar el límite por IP, repite `/ask` más de `ASK_RATE_LIMIT_PER_HOUR` veces (cada pregunta cuesta una fracción de centavo; mejor bajar `ASK_RATE_LIMIT_PER_HOUR` a 3 para la prueba y devolverlo después): la siguiente debe dar 429 con `Retry-After`; `/health` nunca se limita.

## 6. Operación y cuidados

- **Local con n8n:** con el valor por defecto (20/h), un n8n local que llame a `/ask` más de 20 veces por hora recibe 429. En tu `.env` local pon `ASK_RATE_LIMIT_PER_HOUR` más alto o `0`.
- **Cada deploy reinicia el contador** del límite por IP (vive en memoria).
- **Neon** suspende el cómputo tras 5 min sin uso y reactiva en cientos de milisegundos; el plan gratis tiene 1 GB, el corpus ocupa muy poco (estimado en decenas de MB, no medido: míralo en el panel de Neon).
- **Memoria:** el plan de 512 MB corre la API y el subproceso MCP; no se midió. Si Render reinicia el servicio por memoria, mira los logs y sube de plan.
- **Si algo se filtra:** rota la clave en OpenAI (borra la clave del proyecto y crea otra) y la contraseña de la base en Neon, y actualiza las variables en Render.
- **Cambiar de versión de la documentación:** cambia `FASTAPI_DOCS_REF` y repite el paso 3.
