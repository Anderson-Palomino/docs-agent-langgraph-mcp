"""Grafo del agente: clasificar → buscar → evaluar → responder | no_se (D31, D32).

Cada nodo devuelve solo las claves que cambia; LangGraph las mezcla en el estado.
Las herramientas se consumen por MCP (`DocsMCPClient`, D30); las llamadas OpenAI son
síncronas y van en `asyncio.to_thread` para no bloquear el event loop.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from docs_agent.agent.classify import classify_question
from docs_agent.config import Settings
from docs_agent.rag.answer import Citation, answer_question
from docs_agent.rag.retrieve import RetrievedChunk

NO_SE_ANSWERS = {
    "en": "I couldn't find this in the indexed FastAPI documentation, so I won't guess.",
    "es": "No encontré esto en la documentación de FastAPI indexada, así que no voy a inventar una respuesta.",
}

Route = Literal["answer", "no_se"]
Reason = Literal["out_of_domain", "insufficient_context"] | None


class AgentState(TypedDict, total=False):
    question: str
    language: Literal["es", "en"]
    route: Route
    reason: Reason
    results: list[dict]
    best_distance: float | None
    section: dict | None
    answer: str
    citations: list[Citation]
    grounded: bool
    usage: dict[str, int]
    tools_used: list[str]


@dataclass
class AgentDeps:
    openai: Any  # cliente OpenAI síncrono (envuelto con `wrap_openai` por quien lo crea, si hay tracing)
    tools: Any  # objeto con `async call(tool, args) -> dict`, p. ej. `DocsMCPClient`
    settings: Settings
    check_budget: Callable[[], None]  # lanza `BudgetExceeded`


def _empty_usage() -> dict[str, int]:
    return {
        "classifier_prompt_tokens": 0,
        "classifier_completion_tokens": 0,
        "embedding_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }


def _chunks(results: list[dict]) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(id=i, url=r["url"], title=r["title"], content=r["snippet"], distance=r["distance"])
        for i, r in enumerate(results)
    ]


def build_graph(deps: AgentDeps) -> CompiledStateGraph:
    settings = deps.settings

    async def classify(state: AgentState) -> AgentState:
        deps.check_budget()
        c, prompt_tokens, completion_tokens = await asyncio.to_thread(
            classify_question, deps.openai, state["question"], settings.chat_model
        )
        usage = _empty_usage()
        usage["classifier_prompt_tokens"] = prompt_tokens
        usage["classifier_completion_tokens"] = completion_tokens
        return {
            "language": c.language,
            "reason": None if c.is_fastapi else "out_of_domain",
            "usage": usage,
            "tools_used": [],
        }

    async def search(state: AgentState) -> AgentState:
        out = await deps.tools.call("search_docs", {"query": state["question"], "k": settings.top_k})
        usage = {**state["usage"], "embedding_tokens": out.get("embedding_tokens", 0)}
        return {
            "results": out["results"],
            "best_distance": out["best_distance"],
            "usage": usage,
            "tools_used": [*state["tools_used"], "search_docs"],
        }

    async def evaluate(state: AgentState) -> AgentState:
        best = state.get("best_distance")
        enough = bool(state.get("results")) and best is not None and best <= settings.no_answer_distance_threshold
        return {"reason": None if enough else "insufficient_context"}

    async def answer(state: AgentState) -> AgentState:
        deps.check_budget()
        results = state["results"]
        section = await deps.tools.call("get_section", {"url": results[0]["url"]})
        result = await asyncio.to_thread(
            answer_question,
            deps.openai,
            state["question"],
            _chunks(results),
            settings.chat_model,
            section["content"],
        )
        usage = {
            **state["usage"],
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        }
        return {
            "route": "answer",
            "reason": None,
            "section": section,
            "answer": result.answer,
            "citations": result.citations,
            "grounded": result.grounded,
            "usage": usage,
            "tools_used": [*state["tools_used"], "get_section"],
        }

    async def no_se(state: AgentState) -> AgentState:
        return {
            "route": "no_se",
            "answer": NO_SE_ANSWERS[state.get("language", "en")],
            "citations": [],
            "grounded": False,
        }

    def after_classify(state: AgentState) -> str:
        return "no_se" if state["reason"] == "out_of_domain" else "search"

    def after_evaluate(state: AgentState) -> str:
        return "no_se" if state["reason"] == "insufficient_context" else "answer"

    g = StateGraph(AgentState)
    g.add_node("classify", classify)
    g.add_node("search", search)
    g.add_node("evaluate", evaluate)
    g.add_node("answer", answer)
    g.add_node("no_se", no_se)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", after_classify, {"search": "search", "no_se": "no_se"})
    g.add_edge("search", "evaluate")
    g.add_conditional_edges("evaluate", after_evaluate, {"answer": "answer", "no_se": "no_se"})
    g.add_edge("answer", END)
    g.add_edge("no_se", END)
    return g.compile()


def mermaid(graph: CompiledStateGraph) -> str:
    return graph.get_graph().draw_mermaid()
