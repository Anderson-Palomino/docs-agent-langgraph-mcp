"""`scripts/measure_dual_query.py` con `tools` falso: sin OpenAI ni servidor MCP."""

import asyncio
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_dual_query.py"


@pytest.fixture(scope="module")
def md():
    spec = importlib.util.spec_from_file_location("measure_dual_query", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTools:
    """Devuelve distancia y URL fijas por consulta y registra las llamadas."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    async def call(self, tool, args):
        self.calls.append((tool, args))
        dist, url = self.table[args["query"]]
        return {"results": [{"url": url, "distance": dist}], "best_distance": dist, "embedding_tokens": 5}


def case(id_, lang="es", translated=True, route="answer"):
    return {
        "id": id_, "lang": lang, "expected_route": route, "translated": translated,
        "question": f"pregunta {id_}", "search_query": f"query {id_}",
    }


def test_dos_llamadas_por_caso_y_best_from(md):
    tools = FakeTools({
        "pregunta a": (0.50, "u/orig-a"), "query a": (0.30, "u/tr-a"),
        "pregunta b": (0.20, "u/orig-b"), "query b": (0.40, "u/tr-b"),
    })
    rows = asyncio.run(md.measure([case("a"), case("b")], tools))
    assert len(tools.calls) == 4
    assert all(t == "search_docs" for t, _ in tools.calls)
    a, b = rows
    assert a["best_from"] == "translated" and a["distance_translated"] == 0.30
    assert a["top_url_original"] == "u/orig-a" and a["top_url_translated"] == "u/tr-a"
    assert b["best_from"] == "original" and b["distance_original"] == 0.20
    assert a["expected_route"] == "answer"


def test_omite_en_y_sin_traduccion(md):
    tools = FakeTools({"pregunta a": (0.5, "x"), "query a": (0.4, "y")})
    rows = asyncio.run(md.measure([case("a"), case("e", lang="en"), case("n", translated=False)], tools))
    assert [r["id"] for r in rows] == ["a"]
    assert len(tools.calls) == 2


def test_render_dual_una_fila_por_caso(md):
    rows = [
        {"id": "a", "expected_route": "answer", "distance_original": 0.5, "distance_translated": 0.3,
         "top_url_original": "u1", "top_url_translated": "u2", "best_from": "translated"},
        {"id": "b", "expected_route": "out_of_scope", "distance_original": 0.2, "distance_translated": 0.4,
         "top_url_original": "u3", "top_url_translated": "u4", "best_from": "original"},
    ]
    out = md.render_dual(rows)
    lines = [ln for ln in out.splitlines() if ln.startswith("|")]
    assert len(lines) == 2 + 2  # encabezado + separador + 2 filas
    assert "| a |" in out and "| b |" in out and "0.300" in out
