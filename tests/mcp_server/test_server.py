import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client

from docs_agent.budget import record_usage
from docs_agent.config import Settings
from docs_agent.db import connect
from docs_agent.mcp_server.server import INSTRUCTIONS, build_server
from tests.fakes import FakeOpenAI

REPO = Path(__file__).resolve().parents[2]
BODY = "https://fastapi.tiangolo.com/tutorial/body/"


def make_server(**overrides):
    settings = Settings(_env_file=None, **{"openai_api_key": "sk-test", "fastapi_docs_ref": "test-ref", **overrides})
    return build_server(settings, conn_factory=connect, client_factory=FakeOpenAI)


def mcp_lines(capsys) -> list[str]:
    return [line for line in capsys.readouterr().err.splitlines() if line.startswith("[mcp] ")]


def test_main_exits_1_on_invalid_scope():
    env = {**os.environ, "MCP_BUDGET_SCOPE": "x"}
    proc = subprocess.run(
        [sys.executable, "-m", "docs_agent.mcp_server"],
        env=env, cwd=REPO, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
    )
    assert proc.returncode == 1
    assert "invalid MCP_BUDGET_SCOPE: x (expected mcp|ask)" in proc.stderr
    assert proc.stdout == ""


def test_instructions_text():
    assert INSTRUCTIONS.format(ref="0.162.0").startswith(
        "Tools over the indexed FastAPI documentation (version 0.162.0). Answer ONLY with what these tools"
    )


@pytest.mark.anyio
@pytest.mark.integration
async def test_list_tools_and_instructions(seeded_corpus):
    async with Client(make_server()) as c:
        tools = (await c.list_tools()).tools
        assert {t.name for t in tools} == {"list_sources", "search_docs", "get_section"}
        assert all(t.description for t in tools)
        assert "Mentioning is not documenting" in c.instructions
        assert "(version test-ref)" in c.instructions


@pytest.mark.anyio
@pytest.mark.integration
async def test_call_search_docs(seeded_corpus, capsys):
    async with Client(make_server()) as c:
        res = await c.call_tool("search_docs", {"query": "request body"})
    assert res.is_error is False
    assert res.structured_content["results"]
    assert set(res.structured_content) == {"results", "best_distance", "in_corpus", "notice", "embedding_tokens"}
    lines = mcp_lines(capsys)
    assert len(lines) == 1
    assert re.fullmatch(
        r'\[mcp\] search_docs query="request body" k=5 → 2 results · best=\d\.\d{3} · in_corpus=(yes|no) · \d+ ms',
        lines[0],
    ), lines[0]


@pytest.mark.anyio
@pytest.mark.integration
async def test_search_docs_log_truncates_query(seeded_corpus, capsys):
    query = "q" * 100
    async with Client(make_server()) as c:
        await c.call_tool("search_docs", {"query": query, "k": 1})
    (line,) = mcp_lines(capsys)
    assert f'query="{"q" * 60}…" k=1 → 1 result ·' in line


@pytest.mark.anyio
@pytest.mark.integration
async def test_call_get_section_and_list_sources(seeded_corpus, capsys):
    async with Client(make_server()) as c:
        sec = await c.call_tool("get_section", {"url": f"{BODY}#request-body"})
        src = await c.call_tool("list_sources", {})
    assert sec.structured_content["content"].startswith("## Request Body\n")
    assert src.structured_content == {"project": "FastAPI", "version": "test-ref", "pages": 2, "chunks": 2, "sections": 4}
    get_line, list_line = mcp_lines(capsys)
    chars = len(sec.structured_content["content"])
    assert re.fullmatch(rf"\[mcp\] get_section url={re.escape(BODY)}#request-body → 1 section · {chars} chars · \d+ ms", get_line)
    assert re.fullmatch(r"\[mcp\] list_sources → FastAPI test-ref · 2 pages · 2 chunks · \d+ ms", list_line)


@pytest.mark.anyio
@pytest.mark.integration
async def test_get_section_unknown_is_mcp_error(seeded_corpus, capsys):
    url = f"{BODY}#nope"
    async with Client(make_server()) as c:
        res = await c.call_tool("get_section", {"url": url})
    assert res.is_error is True
    assert f"Unknown section URL: {url}. Use search_docs to find valid URLs." in res.content[0].text
    (line,) = mcp_lines(capsys)
    assert re.fullmatch(rf"\[mcp\] get_section url={re.escape(url)} → ERROR Unknown section URL · \d+ ms", line)


@pytest.mark.anyio
@pytest.mark.integration
async def test_search_docs_budget_exhausted_is_mcp_error(seeded_corpus, db_conn, capsys):
    record_usage(db_conn, "mcp", 10)
    async with Client(make_server(mcp_daily_token_budget=10)) as c:
        res = await c.call_tool("search_docs", {"query": "request body"})
    assert res.is_error is True
    assert "daily token budget exceeded: used 10 of 10" in res.content[0].text
    (line,) = mcp_lines(capsys)
    assert "→ ERROR daily token budget exceeded ·" in line


@pytest.mark.anyio
@pytest.mark.integration
async def test_unexpected_error_logs_one_line(seeded_corpus, capsys, monkeypatch):
    from docs_agent.mcp_server import tools

    def boom(*args, **kwargs):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(tools, "list_sources", boom)
    async with Client(make_server()) as c:
        res = await c.call_tool("list_sources", {})
    assert res.is_error is True
    assert "secret detail" not in res.content[0].text
    (line,) = mcp_lines(capsys)
    assert re.fullmatch(r"\[mcp\] list_sources → ERROR RuntimeError · \d+ ms", line), line


@pytest.mark.anyio
@pytest.mark.integration
async def test_search_docs_log_uses_clamped_k(seeded_corpus, capsys):
    async with Client(make_server()) as c:
        await c.call_tool("search_docs", {"query": "x", "k": 50})
    (line,) = mcp_lines(capsys)
    assert " k=10 → 2 results ·" in line
