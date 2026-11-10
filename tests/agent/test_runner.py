"""`invoke_recording`: registrar lo gastado sin tapar el error del grafo (lo usan `/ask` y `demo_check`)."""

import pytest

from docs_agent.agent.runner import invoke_recording


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
