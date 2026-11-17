"""`invoke_recording`: registrar lo gastado sin tapar el error del grafo (lo usan `/ask` y `demo_check`)."""

import pytest

from docs_agent.agent.runner import invoke_recording, make_deps, record_spent
from docs_agent.budget import tokens_used_today
from docs_agent.config import Settings


def test_invoke_recording_keeps_original_error():
    import asyncio

    import psycopg

    warnings: list[str] = []

    async def invoke():
        raise RuntimeError("grafo")

    def record():
        raise psycopg.OperationalError("db caída")

    with pytest.raises(RuntimeError, match="grafo"):
        asyncio.run(invoke_recording(invoke, record, warnings.append))
    assert len(warnings) == 1 and "OperationalError" in warnings[0]


def test_invoke_recording_records_and_propagates_db_error_on_success():
    import asyncio

    import psycopg

    recorded: list[bool] = []

    async def invoke():
        return {"route": "answer"}

    assert asyncio.run(invoke_recording(invoke, lambda: recorded.append(True), lambda m: None)) == {"route": "answer"}
    assert recorded == [True]

    def record():
        raise psycopg.OperationalError("db caída")

    with pytest.raises(psycopg.OperationalError):
        asyncio.run(invoke_recording(invoke, record, lambda m: None))


@pytest.mark.parametrize("kind, limit", [(None, 200_000), ("ask", 200_000), ("eval", 600_000)])
def test_make_deps_checks_budget_of_kind(monkeypatch, kind, limit):
    calls = []
    monkeypatch.setattr("docs_agent.agent.runner.check_budget", lambda conn, k, lim: calls.append((k, lim)))
    kwargs = {} if kind is None else {"kind": kind}
    deps = make_deps(object(), object(), object(), Settings(_env_file=None), **kwargs)
    deps.check_budget()
    assert calls == [(kind or "ask", limit)]


@pytest.mark.integration
def test_record_spent_records_in_kind(db_conn):
    deps = make_deps(db_conn, object(), object(), Settings(_env_file=None), kind="eval")
    deps.spent["chat_tokens"] = 123
    record_spent(db_conn, deps, kind="eval")
    assert tokens_used_today(db_conn, "eval") == 123
    assert tokens_used_today(db_conn, "ask") == 0
    record_spent(db_conn, deps)  # default: ask
    assert tokens_used_today(db_conn, "ask") == 123
