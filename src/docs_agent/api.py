"""API HTTP: POST /ask (RAG con citas validadas) y GET /health."""

from collections.abc import Iterator

import openai
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, field_validator

from docs_agent.budget import KIND_ASK, BudgetExceeded, check_budget, record_usage
from docs_agent.config import get_settings
from docs_agent.db import connect
from docs_agent.ingest.embed import embed_texts
from docs_agent.rag.answer import Citation, answer_question
from docs_agent.rag.retrieve import corpus_size, search

OPENAI_TIMEOUT_S = 30
OPENAI_MAX_RETRIES = 2

app = FastAPI(title="docs-agent")


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
    retrieved: list[dict] | None = None


@app.post("/ask", response_model=AskResponse, response_model_exclude_none=True)
def ask(
    req: AskRequest,
    debug: bool = False,
    conn: psycopg.Connection = Depends(get_conn),
    client: OpenAI = Depends(get_openai),
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
    try:
        vectors, embedding_tokens = embed_texts(client, [req.question], settings.embedding_model)
        chunks = search(conn, vectors[0], settings.fastapi_docs_ref, k=settings.top_k)
        result = answer_question(client, req.question, chunks, settings.chat_model)
    except openai.OpenAIError:
        raise HTTPException(status_code=502, detail="Upstream model error")
    record_usage(conn, KIND_ASK, embedding_tokens + result.prompt_tokens + result.completion_tokens)
    return AskResponse(
        answer=result.answer,
        citations=result.citations,
        grounded=result.grounded,
        usage={
            "embedding_tokens": embedding_tokens,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        },
        retrieved=(
            [{"url": c.url, "title": c.title, "distance": c.distance} for c in chunks] if debug else None
        ),
    )


@app.get("/health")
def health(conn: psycopg.Connection = Depends(get_conn)) -> dict:
    try:
        return {"status": "ok", "chunks": corpus_size(conn, get_settings().fastapi_docs_ref)}
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable")
