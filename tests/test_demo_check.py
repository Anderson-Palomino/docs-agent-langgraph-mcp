"""Funciones puras de `scripts/demo_check.py`: sin OpenAI, sin servidor MCP y sin correr pytest."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "demo_check.py"


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location("demo_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _citation(url: str) -> dict:
    return {"title": "OAuth2", "url": url}


def test_evaluate_expectation_moment1(demo):
    ok = {"route": "tool", "tools_used": ["list_sources"], "sources": {"pages": 3, "chunks": 10, "sections": 5}}
    assert demo.evaluate_expectation(1, ok) is True
    assert demo.evaluate_expectation(1, {**ok, "sources": {"pages": 0, "chunks": 0, "sections": 0}}) is False
    assert demo.evaluate_expectation(1, {**ok, "route": "answer"}) is False


def test_evaluate_expectation_moment2(demo):
    ok = {
        "route": "answer",
        "reason": None,
        "tools_used": ["search_docs", "get_section"],
        "citations": [_citation("https://fastapi.tiangolo.com/tutorial/security/get-current-user/#create-a-user-model")],
    }
    assert demo.evaluate_expectation(2, ok) is True
    assert demo.evaluate_expectation(2, {**ok, "route": "no_se"}) is False
    assert demo.evaluate_expectation(2, {**ok, "tools_used": ["search_docs"]}) is False
    assert demo.evaluate_expectation(2, {**ok, "citations": [_citation("https://fastapi.tiangolo.com/tutorial/body/")]}) is False
    assert demo.evaluate_expectation(2, {**ok, "citations": []}) is False


def test_evaluate_expectation_moment2_accepts_citation_objects(demo):
    from docs_agent.rag.answer import Citation

    state = {
        "route": "answer",
        "tools_used": ["search_docs", "get_section"],
        "citations": [Citation(title="OAuth2", url="https://fastapi.tiangolo.com/tutorial/security/first-steps/")],
    }
    assert demo.evaluate_expectation(2, state) is True


def test_evaluate_expectation_moment3(demo):
    ok = {"route": "no_se", "reason": "out_of_domain", "tools_used": [], "citations": []}
    assert demo.evaluate_expectation(3, ok) is True
    assert demo.evaluate_expectation(3, {**ok, "reason": "insufficient_context"}) is False
    assert demo.evaluate_expectation(3, {**ok, "route": "answer", "reason": None}) is False


def test_evaluate_expectation_unknown_moment(demo):
    with pytest.raises(ValueError):
        demo.evaluate_expectation(4, {})


def test_parse_passed(demo):
    assert demo.parse_passed("54 passed, 2 skipped in 3.1s") == 54
    assert demo.parse_passed("===== 1 failed, 175 passed in 20.01s =====") == 175
    assert demo.parse_passed("no tests ran in 0.01s") is None


def test_parse_passed_uses_last_match(demo):
    output = (
        "F.....\n"
        "E   AssertionError: assert '54 passed' in captured\n"
        "===== 1 failed, 188 passed in 30.00s =====\n"
    )
    assert demo.parse_passed(output) == 188


def test_run_pytest_timeout(demo, monkeypatch):
    import subprocess

    def boom(*a, **kw):
        assert kw["timeout"] == demo.PYTEST_TIMEOUT_S
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=kw["timeout"])

    monkeypatch.setattr(demo.subprocess, "run", boom)
    assert demo._run_pytest({}) == (None, True)


@pytest.mark.parametrize("q", ["", "   ", "x" * 1001])
def test_q_rejects_empty_or_too_long(demo, q):
    with pytest.raises(SystemExit) as exc:
        demo.main(["--q", q, "--skip-tests"])
    assert exc.value.code == 2  # argparse.error


def test_invoke_recording_keeps_original_error(demo):
    import asyncio

    import psycopg

    warnings: list[str] = []

    async def invoke():
        raise RuntimeError("grafo")

    def record():
        raise psycopg.OperationalError("db caída")

    with pytest.raises(RuntimeError, match="grafo"):
        asyncio.run(demo.invoke_recording(invoke, record, warnings.append))
    assert len(warnings) == 1 and "OperationalError" in warnings[0]


def test_invoke_recording_records_and_propagates_db_error_on_success(demo):
    import asyncio

    import psycopg

    recorded: list[bool] = []

    async def invoke():
        return {"route": "answer"}

    assert asyncio.run(demo.invoke_recording(invoke, lambda: recorded.append(True), lambda m: None)) == {"route": "answer"}
    assert recorded == [True]

    def record():
        raise psycopg.OperationalError("db caída")

    with pytest.raises(psycopg.OperationalError):
        asyncio.run(demo.invoke_recording(invoke, record, lambda m: None))


def test_render_has_columns(demo):
    table = demo.render([], {"total_cost_usd": 0.0, "avg_latency_ms": 0.0, "tests_passed": None})
    assert [c.header for c in table.columns] == [
        "Pregunta",
        "Ruta",
        "Herramientas",
        "Tokens",
        "Costo USD",
        "Latencia ms",
        "✓/✗",
    ]


def test_render_rows_and_mark(demo):
    rows = [
        demo.Row("¿Qué documentación tienes disponible?", "tool", ["list_sources"], 0, 0.0, 12.0, True),
        demo.Row("pregunta libre", "answer", ["search_docs", "get_section"], 1500, 0.0012, 2300.0, None),
        demo.Row("fuera de dominio", "no_se · out_of_domain", [], 120, 0.00005, 800.0, False),
    ]
    table = demo.render(rows, {"total_cost_usd": 0.00125, "avg_latency_ms": 1037.3, "tests_passed": 176})
    assert table.row_count == 3
    marks = [str(c) for c in table.columns[-1].cells]
    assert marks == ["✓", "", "✗"]
