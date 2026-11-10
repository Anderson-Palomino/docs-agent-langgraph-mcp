"""Imprime el diagrama Mermaid del grafo del agente (se pega tal cual en el README).

Uso: uv run python scripts/export_mermaid.py
Usa dependencias falsas: no toca OpenAI, Postgres ni el servidor MCP, y no lee `.env`.
"""

from docs_agent.agent.graph import AgentDeps, build_graph, mermaid
from docs_agent.config import Settings


def main() -> None:
    deps = AgentDeps(
        openai=None,
        tools=None,
        settings=Settings(_env_file=None, openai_api_key="unused"),
        check_budget=lambda: None,
    )
    print(mermaid(build_graph(deps)))


if __name__ == "__main__":
    main()
