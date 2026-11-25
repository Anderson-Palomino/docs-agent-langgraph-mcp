# Guion del video de demo (2 minutos)

Objetivo: que un reclutador técnico vea, en 2 minutos, que el agente responde con citas, sabe decir "no sé", está medido y expone su propio servidor MCP. Hablar en español o inglés, pero mantener un solo idioma en todo el video.

Antes de grabar: abrir la demo en vivo y hacer una pregunta para despertar el servicio (el plan gratis de Render tarda cerca de un minuto en arrancar en frío). Tener lista una terminal en `demo/` con `claude mcp list` mostrando `docs-agent` conectado, y la tabla de evaluación del README abierta. Ensayar con `uv run python scripts/demo_check.py`.

| Tramo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00-0:20 | README, diagrama de arquitectura | Qué es: un agente que responde sobre la doc de FastAPI, en español o inglés, citando la sección exacta. API FastAPI, grafo LangGraph, servidor MCP propio, Postgres con pgvector. |
| 0:20-0:55 | Swagger de la demo en vivo, `POST /ask` con una pregunta en español (por ejemplo, "¿Cómo agrego CORS a mi aplicación FastAPI?") | La respuesta llega en español, con las citas a la sección de la doc. Mostrar que `grounded` es `true` y abrir una de las URLs citadas. Mencionar que la pregunta se tradujo para buscar en un corpus en inglés. |
| 0:55-1:15 | Misma pantalla, una pregunta fuera del corpus (por ejemplo, Django REST Framework) | Responde "no sé" (`route: "no_se"`) en lugar de inventar. Es parte del diseño: el clasificador y el umbral de distancia cortan antes de responder. |
| 1:15-1:35 | Tabla de evaluación del README | El holdout en español es la medición limpia: 4 de 6 rutas correctas, 0 falsos "respondí". El golden set de 30 casos va aparte porque el prompt de traducción se ajustó mirando esos casos. Decir las limitaciones: 6 casos son pocos y la revisión manual del juez sigue pendiente. |
| 1:35-2:00 | Terminal en `demo/`, Claude Code con el servidor MCP | Claude usa `search_docs` del servidor propio y responde solo con lo que devuelve; ante una pregunta fuera del corpus dice que la doc indexada no la cubre. Aclarar que esa política vive en `demo/CLAUDE.md` porque un servidor MCP ofrece herramientas pero no puede obligar al cliente a usarlas (D35). |

Cierre (últimos segundos): decisiones y limitaciones están en `docs/decisiones.md`.

Notas para no tropezar:

- La demo en vivo limita `/ask` a 20 pedidos por hora por IP; no repetir pruebas en la grabación.
- Si el servicio estaba dormido, cortar la espera en edición.
- Las cifras que se digan deben ser las del README (vienen de `eval/results/`); no improvisar otras.
