"""API HTTP: POST /ask (grafo del agente sobre el servidor MCP, D30-D33) y GET /health."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import openai
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from openai import OpenAI
from pydantic import BaseModel, field_validator, model_serializer

from docs_agent.agent.graph import AgentDeps, _is_budget_error, build_graph
from docs_agent.agent.mcp_client import DocsMCPClient, DocsServerUnavailable, DocsToolError, stdio_connect
from docs_agent.budget import KIND_ASK, BudgetExceeded, check_budget, record_usage
from docs_agent.config import get_settings
from docs_agent.db import connect
from docs_agent.rag.answer import Citation
from docs_agent.rag.retrieve import corpus_size

OPENAI_TIMEOUT_S = 30
OPENAI_MAX_RETRIES = 2


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Un cliente MCP por proceso; perezoso: el servidor stdio (scope `ask`, D29) arranca en la primera llamada."""
    settings = get_settings()
    docs_tools = DocsMCPClient(stdio_connect(settings, "ask"), settings.mcp_call_timeout_s)
    app.state.docs_tools = docs_tools
    try:
        yield
    finally:
        await docs_tools.aclose()


app = FastAPI(title="docs-agent", lifespan=lifespan)


def get_conn() -> Iterator[psycopg.Connection]:
    try:
        conn = connect()
    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        yield conn
    finally:
        conn.close()


def get_openai() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key.get_secret_value(), timeout=OPENAI_TIMEOUT_S, max_retries=OPENAI_MAX_RETRIES)


def get_docs_tools(request: Request) -> Any:
    """El `DocsMCPClient` del lifespan; los tests lo sobrescriben."""
    return request.app.state.docs_tools


class AskRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 1000:
            raise ValueError("question must be 1..1000 characters")
        return v


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool
    usage: dict[str, int]
    route: str  # "answer" | "no_se" (D33)
    reason: str | None = None  # None | "out_of_domain" | "insufficient_context"; siempre presente, null si answer
    retrieved: list[dict] | None = None

    @model_serializer(mode="wrap")
    def _omit_missing_retrieved(self, handler):
        # `retrieved` solo aparece con ?debug=true; `reason` sí viaja como null.
        data = handler(self)
        if data.get("retrieved") is None:
            data.pop("retrieved", None)
        return data


@app.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest,
    debug: bool = False,
    conn: psycopg.Connection = Depends(get_conn),
    client: OpenAI = Depends(get_openai),
    docs_tools: Any = Depends(get_docs_tools),
) -> AskResponse:
    settings = get_settings()
    if not settings.openai_api_key.get_secret_value():
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    try:
        check_budget(conn, KIND_ASK, settings.ask_daily_token_budget)
    except BudgetExceeded:
        raise HTTPException(status_code=429, detail="Daily token budget exhausted")
    if corpus_size(conn, settings.fastapi_docs_ref) == 0:
        raise HTTPException(status_code=503, detail="Corpus is empty: run the ingest command first")

    deps = AgentDeps(
        openai=client,
        tools=docs_tools,
        settings=settings,
        check_budget=lambda: check_budget(conn, KIND_ASK, settings.ask_daily_token_budget),
    )
    try:
        state = await build_graph(deps).ainvoke({"question": req.question})
    except BudgetExceeded:
        raise HTTPException(status_code=429, detail="Daily token budget exhausted")
    except DocsServerUnavailable:  # incluye DocsToolTimeout
        raise HTTPException(status_code=503, detail="Docs server unavailable")
    except DocsToolError as exc:
        if _is_budget_error(exc):
            raise HTTPException(status_code=429, detail="Daily token budget exhausted")
        raise HTTPException(status_code=502, detail="Docs tool error")
    except openai.OpenAIError:
        raise HTTPException(status_code=502, detail="Upstream model error")

    usage = state["usage"]
    classifier_tokens = usage["classifier_prompt_tokens"] + usage["classifier_completion_tokens"]
    # Solo lo que gastó la API; los embeddings ya los registró el servidor MCP en el mismo kind (scope `ask`).
    record_usage(conn, KIND_ASK, classifier_tokens + usage["prompt_tokens"] + usage["completion_tokens"])
    return AskResponse(
        answer=state["answer"],
        citations=state["citations"],
        grounded=state["grounded"],
        usage={
            "embedding_tokens": usage["embedding_tokens"],
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "classifier_tokens": classifier_tokens,
        },
        route=state["route"],
        reason=state.get("reason"),
        retrieved=(
            [{"url": r["url"], "title": r["title"], "distance": r["distance"]} for r in state.get("results", [])]
            if debug
            else None
        ),
    )


@app.get("/health")
def health(conn: psycopg.Connection = Depends(get_conn)) -> dict:
    try:
        return {"status": "ok", "chunks": corpus_size(conn, get_settings().fastapi_docs_ref)}
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable")
