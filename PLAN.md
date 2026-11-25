# docs-agent-langgraph-mcp — Plan de proyecto

## Contexto
Proyecto de portafolio para postular a roles de AI Engineer. Objetivo: demostrar LangGraph, RAG y un servidor MCP propio, con evaluación medida y despliegue. 4 semanas, 5–7 h por semana.

Soy desarrollador Full Stack (Python/FastAPI, React/TypeScript, PostgreSQL, AWS, Docker). Ya usé OpenAI en producción con salidas estructuradas y golden set. Lo nuevo para mí es LangGraph, RAG con pgvector y construir servidores MCP.

## Reglas para Claude Code
- Trabaja una semana a la vez con el flujo completo de superpowers, sin saltar fases: brainstorming → plan → ejecución → code review → cerrar la rama. Puedes usar subagentes en la ejecución.
- Después voy a estudiar el código para explicarlo en entrevistas. En cada decisión técnica importante, anota en docs/decisiones.md qué se eligió, qué alternativas había y por qué.
- Solo datos públicos. Nada de datos de empleadores ni clientes.
- Commits pequeños con mensajes claros. Tests con pytest en cada paso.
- Pon un límite de gasto de tokens configurable por variable de entorno.

## Stack
| Pieza | Herramienta |
| --- | --- |
| Orquestación del agente | LangGraph |
| RAG | PostgreSQL + pgvector |
| Modelo y embeddings | OpenAI gpt-4.1-mini + text-embedding-3-small |
| Servidor MCP | SDK oficial de MCP en Python |
| API | FastAPI |
| Empaquetado | Docker Compose |
| Trazas | LangSmith (plan gratuito) o Langfuse |

Corpus: documentación técnica pública (por ejemplo, la doc de FastAPI o de AWS SQS).

## Alcance mínimo
- Endpoint `/ask` que responde citando la URL de origen.
- 2–3 herramientas expuestas por MCP.
- Golden set de 30 preguntas con script de evaluación.
- README en inglés con demo.

## Semana 1 (2–8 nov): RAG con citas
1. Repo con FastAPI + Postgres/pgvector en Docker Compose.
2. Script de ingesta: descargar la doc, dividirla en fragmentos, generar embeddings y guardarlos.
3. `/ask`: buscar los 5 fragmentos más cercanos y responder citando la fuente.

Hecho cuando: `docker compose up` funciona y 5 preguntas de ejemplo se responden con su cita.

## Semana 2 (9–15 nov): agente + servidor MCP
1. Pasar `/ask` a un grafo de LangGraph: clasificar → buscar (RAG) → responder, con una rama de "no sé" cuando el contexto no alcanza.
2. Servidor MCP con `search_docs`, `get_section` y `list_sources`.
3. El agente usa ese servidor como cliente MCP. Probarlo también desde Claude Code / Claude Desktop.
4. Tests con pytest de las tools y del flujo del grafo.

Hecho cuando: Claude usa el servidor MCP en una demo grabada y el README tiene el diagrama del grafo.

## Semana 3 (16–22 nov): evaluación, trazas y despliegue
1. Golden set de 30 preguntas: respuesta esperada y fuente correcta.
2. Script de evaluación: fuente correcta, fidelidad al contexto y aciertos de "no sé".
3. Trazas con LangSmith o Langfuse (pasos, tokens, latencia).
4. Despliegue en Render, Railway o Fly.io con límite de gasto.

Hecho cuando: el README tiene la tabla de resultados y un link de demo en vivo.

## Semana 4 (23–29 nov): README y demo
1. README en inglés: qué hace, arquitectura, cómo levantarlo, tabla de evaluación y decisiones técnicas.
2. Video de demo de 2 minutos.

## Checklist
- [x] S1: repo público con Docker Compose y RAG con citas
- [x] S2: grafo de LangGraph funcionando
- [x] S2: servidor MCP propio probado desde Claude
- [x] S3: golden set de 30 preguntas y tabla de resultados
- [x] S3: demo desplegada
- [ ] S3: trazas en la demo (código listo, D34; LangSmith no configurado en Render)
- [x] S4: preguntas en español con traducción en el clasificador, medidas con un holdout (D40, D41); desplegado el 2026-11-25 (PR #6)
- [x] S4: README final en inglés con tabla de evaluación (holdout aparte del golden set) y limitaciones
- [x] S4: guion del video de 2 minutos (`docs/demo-script.md`)
- [x] S4: revisión manual de los casos del juez (`eval/results/2026-11-25-judge-review.md`: 56/56 afirmaciones y 9/9 casos coinciden; D38)
- [ ] S4: grabar el video de 2 minutos
- [x] S4: PR #6 abierto, revisado y mergeado por el dueño (2026-11-25, `ca23d0d`; mergear = desplegar en Render)
- [x] S4: verificación externa de la demo en vivo tras el deploy (`/health`, pregunta en español y en inglés con citas, una fuera del corpus con "no sé"; `docs/deploy.md`)
- [x] S4: prueba del 429 por el dueño y conclusión de D37: la clave pasó de un salto interno de Render a la IP del cliente (`TRUSTED_PROXY_HOPS=2`, PR #7); A/B/C verificados en Render el 2026-11-25
- [ ] S5 (pendiente): recalibrar el umbral con un holdout nuevo y estudiar el fallo de recuperación de h04 (D41)
- [ ] S5 (pendiente): detalles menores de las revisiones de la S4, diferidos por la revisión final (ninguno bloquea; tocan herramientas de evaluación, tests o forma):
  - Holdout y golden: test de que las `expected_urls` del holdout no se cruzan con las del golden set; tests de `main(["--holdout"])` por CLI; `--holdout` con la ruta del golden por defecto silencia el chequeo de distribución; `--only` junto con `--holdout` es redundante.
  - Clasificador y grafo: el test fuera de dominio del grafo solo comprueba que existan las claves, no sus valores; el test importa la función privada `openai.lib._pydantic.to_strict_json_schema` (comentarlo); imports repetidos dentro de los tests de `test_classify.py`; la llamada al clasificador no tiene `max_tokens` (la acotan el timeout y el presupuesto).
  - Filas de evaluación: falta un test de que una fila con error deja `language`/`search_query`/`translated` en None; el test de la búsqueda extra en inglés no comprueba `search_query`; una línea de ~130 caracteres.
  - Comparación de corridas: la sección de español no muestra `search_query`/`translated`; distancias iguales salen "no" (mejor "igual"); assert débil de g03 en `test_compare.py`; usa funciones privadas de `report.py`/`metrics.py`; la salida por defecto pisa `<día>-comparison.md`; una fila con error puede esconder un falso «respondí» en los cambios de ruta.
  - Hoja del juez: el bloque `<details>` sale aunque el fragmento no esté truncado; una línea de 4 comillas invertidas en la doc podría desincronizar el parser; filas como `| 1a |` o `| #1 |` se saltan en silencio; un `|` sin escapar en una afirmación muestra un texto crudo confuso.
  - Búsqueda doble: si el presupuesto `eval` se agota a mitad de corrida se pierden las filas parciales; faltan tests de `main`/`_run` y del caso sin `best_distance`.
  - Límite por IP: `mask_ip` muestra redes que no son /64 con sufijo /64; faltan tests de API para las líneas de log con origen `peer`, no-IP e IPv6; con varios workers cada uno tiene su propia sal de `key_id` (hoy hay uno solo); la marca `…` del log no es ASCII; el chequeo `n/a` de `cf_ip_match` se apoya en la cadena `<no-ip>` de `mask_ip`.
