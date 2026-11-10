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
