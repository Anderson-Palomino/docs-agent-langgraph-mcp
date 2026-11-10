"""Cableado común para correr el grafo con presupuesto: lo usan `/ask` y `scripts/demo_check.py`.

Quien invoca sigue llamando a `build_graph(deps).ainvoke(...)` y traduce los errores a su manera (HTTP en la
API, código de salida en el script); aquí solo vive lo que ambos deben hacer igual.
"""

from typing import Any

import psycopg

from docs_agent.agent.graph import AgentDeps
from docs_agent.budget import KIND_ASK, check_budget, record_usage
from docs_agent.config import Settings

RUN_NAME = "ask"


def make_deps(conn: psycopg.Connection, client: Any, tools: Any, settings: Settings) -> AgentDeps:
    """Dependencias del grafo con el chequeo de presupuesto `ask` (el servidor MCP usa el mismo kind, D29)."""
    return AgentDeps(
        openai=client,
        tools=tools,
        settings=settings,
        check_budget=lambda: check_budget(conn, KIND_ASK, settings.ask_daily_token_budget),
    )


def invoke_config(question: str, **metadata: Any) -> dict:
    """Config de `ainvoke`: la corrida se llama `ask` y lleva la pregunta en metadata (D34).

    La ruta solo se conoce al final: route/reason quedan en las outputs de la corrida, no en su metadata.
    """
    return {"run_name": RUN_NAME, "metadata": {"question": question, **metadata}}


def record_spent(conn: psycopg.Connection, deps: AgentDeps) -> None:
    """Registra los tokens de chat ya gastados (clasificador y respuesta, solo llamadas que volvieron).

    Va en un `finally`: cuenta también si el grafo falló. Los embeddings los registró el servidor MCP en el
    mismo kind (scope `ask`).
    """
    if deps.spent["chat_tokens"]:
        record_usage(conn, KIND_ASK, deps.spent["chat_tokens"])
