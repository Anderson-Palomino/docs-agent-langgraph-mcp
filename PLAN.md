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
- [ ] S1: repo público con Docker Compose y RAG con citas
- [ ] S2: grafo de LangGraph funcionando
- [ ] S2: servidor MCP propio probado desde Claude
- [ ] S3: golden set de 30 preguntas y tabla de resultados
- [ ] S3: trazas activas y demo desplegada
- [ ] S4: README en inglés y video de 2 minutos
