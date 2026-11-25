"""`scripts/evaluate.py` con el LLM y las herramientas falsos: sin OpenAI, sin servidor MCP, sin LangSmith."""

import importlib.util
import io
import json
from datetime import date
from pathlib import Path

import pytest
from rich.console import Console

from docs_agent.agent.mcp_client import DocsServerUnavailable, DocsToolError
from docs_agent.budget import record_usage, tokens_used_today
from docs_agent.config import Settings
from docs_agent.evaluation.golden import GoldenCase
from tests.fakes import FakeOpenAI

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate.py"
GOLDEN = Path(__file__).resolve().parents[1] / "eval" / "golden_set.json"

BODY = "https://fastapi.tiangolo.com/tutorial/body/"
QUERY = "https://fastapi.tiangolo.com/tutorial/query-params/"
Q_ANSWER = "How do I declare a request body?"
Q_OUT = "How do I bake a pizza?"  # el clasificador la corta
Q_THRESHOLD = "How do I configure Django REST Framework permissions?"  # la corta el umbral
Q_FLASK = "Flask blueprint"  # consulta en inglés que el clasificador devuelve para una pregunta en español
Q_REQ_BODY = "request body"
BEST = {Q_ANSWER: 0.30, Q_OUT: 0.80, Q_THRESHOLD: 0.70, Q_FLASK: 0.85, Q_REQ_BODY: 0.30}
SECTION = {"url": BODY, "title": "Request Body", "content": "FULL SECTION TEXT about Pydantic models as body"}
CHAT_TOKENS = 120  # FakeOpenAI: 100 de entrada + 20 de salida por llamada de chat


@pytest.fixture(scope="module")
def ev():
    spec = importlib.util.spec_from_file_location("evaluate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PerQuestionOpenAI(FakeOpenAI):
    """El clasificador responde `is_fastapi=False` solo para la pregunta de cocina."""

    def _parse_chat(self, model, messages, response_format, temperature=None):
        from docs_agent.agent.classify import Classification

        from docs_agent.evaluation.judge import _JudgeOutput

        if response_format is Classification:
            self.is_fastapi = messages[-1]["content"] != Q_OUT
        if response_format is _JudgeOutput and getattr(self, "judge_fail", False):
            import openai

            raise openai.OpenAIError("judge down")
        return super()._parse_chat(model, messages, response_format, temperature)


class QuestionTools:
    """Doble de `DocsMCPClient` que responde según la pregunta; `raises` = {pregunta: excepción}."""

    def __init__(self, raises: dict | None = None):
        self.raises = raises or {}
        self.calls: list[tuple[str, dict]] = []

    async def call(self, tool: str, args: dict) -> dict:
        self.calls.append((tool, args))
        if tool == "get_section":
            return SECTION
        query = args["query"]
        if query in self.raises:
            raise self.raises[query]
        best = BEST[query]
        results = [
            {"title": "Request Body", "url": BODY, "distance": best, "snippet": "s",
             "content": "body FULL CHUNK"},
            {"title": "Query Parameters", "url": QUERY, "distance": best + 0.1, "snippet": "s",
             "content": "query FULL CHUNK"},
        ]
        return {"results": results, "best_distance": best, "in_corpus": True, "notice": None, "embedding_tokens": 7}


def golden_cases() -> list[GoldenCase]:
    common = {"lang": "en", "notes": ""}
    return [
        GoldenCase(id="g01", question=Q_ANSWER, category="in_basic", expected_route="answer",
                   expected_urls=[BODY], judge_review=True, **common),
        GoldenCase(id="g02", question=Q_OUT, category="out_obvious", expected_route="no_se",
                   expected_urls=[], **common),
        GoldenCase(id="g03", question=Q_THRESHOLD, category="out_near", expected_route="no_se",
                   expected_urls=[], **common),
    ]


def settings() -> Settings:
    return Settings(_env_file=None, top_k=5, no_answer_distance_threshold=0.52, chat_model="m")


def run(ev, db_conn, *, client=None, tools=None, judge=True, max_tokens=400_000):
    import asyncio

    console = Console(file=io.StringIO())
    return asyncio.run(
        ev.run_cases(
            golden_cases(), settings(), db_conn, client or PerQuestionOpenAI(), tools or QuestionTools(),
            judge=judge, max_tokens=max_tokens, console=console,
        )
    )


def _run_one(ev, db_conn, case_id, client, tools):
    import asyncio

    case = next(c for c in golden_cases() if c.id == case_id)
    console = Console(file=io.StringIO())
    results, aborted = asyncio.run(
        ev.run_cases([case], settings(), db_conn, client, tools, judge=False, max_tokens=400_000, console=console)
    )
    assert aborted is None
    return results[0]


def test_row_records_language_search_query_and_translated(ev, db_conn):
    row = _run_one(ev, db_conn, "g01", PerQuestionOpenAI(language="es", search_query=Q_REQ_BODY), QuestionTools())
    assert (row["language"], row["search_query"], row["translated"]) == ("es", Q_REQ_BODY, True)


def test_out_of_domain_extra_search_uses_search_query(ev, db_conn):
    tools = QuestionTools()
    row = _run_one(ev, db_conn, "g02", PerQuestionOpenAI(language="es", search_query=Q_FLASK), tools)
    assert ("search_docs", {"query": Q_FLASK, "k": 5}) in tools.calls
    assert row["best_distance"] == 0.85 and row["search_query"] == Q_FLASK


def test_out_of_domain_extra_search_english_uses_question(ev, db_conn):
    tools = QuestionTools()
    row = _run_one(ev, db_conn, "g02", PerQuestionOpenAI(language="en"), tools)
    assert ("search_docs", {"query": Q_OUT, "k": 5}) in tools.calls
    assert row["language"] == "en" and row["translated"] is False


def _two_case_file(tmp_path: Path) -> Path:
    """Dos casos válidos: no cumplen la distribución de 30 del golden set."""
    cases = [
        {"id": f"h{i:02d}", "question": f"pregunta {i}", "lang": "es", "category": "in_basic",
         "expected_route": "answer", "expected_urls": [BODY], "notes": "n"}
        for i in (1, 2)
    ]
    path = tmp_path / "holdout.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    return path


def test_select_cases_holdout_skips_distribution(ev, tmp_path):
    from docs_agent.evaluation.golden import GoldenSetError

    path = _two_case_file(tmp_path)
    assert [c.id for c in ev.select_cases(path, None, holdout=True)] == ["h01", "h02"]
    with pytest.raises(GoldenSetError, match="distribución"):
        ev.select_cases(path, None, holdout=False)


def test_run_cases_three_cases(ev, db_conn):
    tools = QuestionTools()
    results, aborted = run(ev, db_conn, tools=tools)
    assert aborted is None
    by_id = {r["id"]: r for r in results}
    assert [r["id"] for r in results] == ["g01", "g02", "g03"]

    a, cls, thr = by_id["g01"], by_id["g02"], by_id["g03"]
    assert (a["route"], a["reason"], a["is_fastapi"]) == ("answer", None, True)
    assert a["citations"] == [BODY] and a["grounded"] is True
    assert a["best_distance"] == 0.30 and a["retrieved_urls"] == [BODY, QUERY]
    assert a["latency_ms"] > 0
    assert "FULL SECTION TEXT" in a["judge_context"]  # lo que vio el juez: la sección en lugar del 1er fragmento
    assert a["context_parts"][0] == {"n": 1, "title": "Request Body", "url": BODY, "section": True}
    assert a["judge"] == {
        "score": 1.0, "unsupported_claims": [], "reason": "fake", "claims": [{"text": "claim", "supported": True}],
    }
    assert a["judge_tokens"] == CHAT_TOKENS and a["judge_cost_usd"] > 0

    # Cortado por el clasificador: la ruta sigue no_se, pero la búsqueda extra dio best_distance y URLs.
    assert (cls["route"], cls["reason"], cls["is_fastapi"]) == ("no_se", "out_of_domain", False)
    assert cls["best_distance"] == 0.80 and cls["retrieved_urls"] == [BODY, QUERY]
    assert cls["usage"]["embedding_tokens"] == 7  # la búsqueda extra suma al costo del caso
    assert cls["judge"] is None and cls["judge_context"] is None
    assert ("search_docs", {"query": Q_OUT, "k": 5}) in tools.calls

    assert (thr["route"], thr["reason"], thr["is_fastapi"]) == ("no_se", "insufficient_context", True)
    assert thr["best_distance"] == 0.70 and thr["judge"] is None
    assert all(r["error"] is None for r in results)

    # Chat (clasificador ×3 + respuesta) y juez quedan en `eval`; `ask` intacto.
    assert tokens_used_today(db_conn, "eval") == CHAT_TOKENS * 5
    assert tokens_used_today(db_conn, "ask") == 0


def test_run_cases_no_judge(ev, db_conn):
    client = PerQuestionOpenAI()
    results, aborted = run(ev, db_conn, client=client, judge=False)
    assert aborted is None
    assert all(r["judge"] is None for r in results)
    assert len([c for c in client.calls if "messages" in c]) == 4  # sin llamadas del juez


def test_run_cases_max_tokens_aborts(ev, db_conn):
    results, aborted = run(ev, db_conn, max_tokens=1)
    assert aborted == "max_tokens"
    assert len(results) == 1 and results[0]["id"] == "g01"


def test_run_cases_tool_error_continues(ev, db_conn):
    tools = QuestionTools(raises={Q_THRESHOLD: DocsServerUnavailable("down")})
    results, aborted = run(ev, db_conn, tools=tools)
    assert aborted is None and len(results) == 3
    by_id = {r["id"]: r for r in results}
    assert by_id["g03"]["error"] == "DocsServerUnavailable"
    assert by_id["g03"]["tokens"] == CHAT_TOKENS  # el clasificador ya había gastado
    assert by_id["g01"]["error"] is None and by_id["g01"]["route"] == "answer"
    assert by_id["g02"]["error"] is None and by_id["g02"]["route"] == "no_se"


def test_run_cases_extra_search_error_keeps_graph_result(ev, db_conn):
    tools = QuestionTools(raises={Q_OUT: DocsServerUnavailable("down")})
    results, _ = run(ev, db_conn, tools=tools)
    cls = {r["id"]: r for r in results}["g02"]
    assert cls["error"] == "DocsServerUnavailable"
    assert cls["route"] == "no_se" and cls["tokens"] == CHAT_TOKENS


def test_run_cases_judge_refusal(ev, db_conn):
    client = PerQuestionOpenAI(judge_refusal=True)
    results, aborted = run(ev, db_conn, client=client)
    assert aborted is None and len(results) == 3
    a = results[0]
    assert a["route"] == "answer" and a["judge"] is None and a["judge_error"] == "JudgeError"
    assert a["error"] is None
    # el rechazo gastó tokens: cuentan en el caso, en el tope y en el presupuesto `eval`
    assert a["judge_tokens"] == CHAT_TOKENS and a["judge_cost_usd"] > 0
    assert tokens_used_today(db_conn, "eval") == CHAT_TOKENS * 5


def test_run_cases_judge_openai_error(ev, db_conn):
    client = PerQuestionOpenAI()
    client.judge_fail = True
    results, aborted = run(ev, db_conn, client=client)
    assert aborted is None and len(results) == 3
    a = results[0]
    assert a["judge_error"] == "OpenAIError" and a["error"] is None and a["route"] == "answer"
    assert ev.exit_code(results, aborted, judge=True) == 1  # el juez falló: la fidelidad quedó incompleta


def test_run_cases_unexpected_error_marks_case(ev, db_conn):
    import asyncio

    tools = QuestionTools(raises={Q_OUT: RuntimeError("boom")})
    partial: list[dict] = []
    with pytest.raises(RuntimeError):
        asyncio.run(ev.run_cases(golden_cases(), settings(), db_conn, PerQuestionOpenAI(), tools, judge=True,
                                 max_tokens=400_000, console=Console(file=io.StringIO()), results=partial))
    assert [r["id"] for r in partial] == ["g01", "g02"]
    assert partial[1]["error"] == "RuntimeError" and partial[1]["tokens"] == CHAT_TOKENS


def test_run_cases_budget_aborts(ev, db_conn):
    record_usage(db_conn, "eval", settings().eval_daily_token_budget)
    results, aborted = run(ev, db_conn)
    assert aborted == "budget"
    assert len(results) == 1 and results[0]["error"] == "BudgetExceeded"


def test_run_cases_mcp_budget_error_aborts(ev, db_conn):
    tools = QuestionTools(raises={Q_ANSWER: DocsToolError("daily token budget exceeded: used 9 of 9")})
    results, aborted = run(ev, db_conn, tools=tools)
    assert aborted == "budget" and len(results) == 1 and results[0]["error"] == "DocsToolError"


# --- salidas ---


def test_write_outputs_suma_errores_y_comparte_stem(ev, db_conn, tmp_path):
    tools = QuestionTools(raises={Q_THRESHOLD: DocsServerUnavailable("down")})
    results, aborted = run(ev, db_conn, tools=tools)
    (tmp_path / "2026-11-18.json").write_text("{}", encoding="utf-8")
    run_info = ev.build_run_info(settings(), date(2026, 11, 18), GOLDEN, None, 400_000, True, aborted, results)
    paths = ev.write_outputs(tmp_path, date(2026, 11, 18), run_info, results, golden_cases())
    assert [p.name for p in paths] == ["2026-11-18-2.json", "2026-11-18-2.md"]
    assert not list(tmp_path.glob("*judge-review*"))
    data = json.loads(paths[0].read_text(encoding="utf-8"))
    assert set(data) == {"run", "cases", "metrics", "sweep"}
    expected_tokens = sum(r["tokens"] + r["judge_tokens"] for r in results)
    assert data["run"]["tokens_total"] == expected_tokens
    assert data["metrics"]["n_errors"] == 1
    # El total de todos los casos incluye lo gastado por el caso con error; el de las métricas no.
    assert data["run"]["cost_total_usd_all"] > data["metrics"]["cost_total_usd"]
    assert "3 casos (2 sin error · 1 error)" in paths[1].read_text(encoding="utf-8")


# --- validación del golden set antes de abrir OpenAI/MCP ---


@pytest.fixture
def no_openai(monkeypatch):
    from docs_agent import api

    def boom(*a, **kw):
        raise AssertionError("no debe construir el cliente OpenAI")

    monkeypatch.setattr(api, "make_openai", boom)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def test_main_rejects_invalid_golden(ev, tmp_path, no_openai, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{no es json", encoding="utf-8")
    assert ev.main(["--golden", str(bad)]) == 1
    small = tmp_path / "small.json"
    small.write_text(json.dumps([c.model_dump() for c in golden_cases()]), encoding="utf-8")
    assert ev.main(["--golden", str(small)]) == 1  # distribución: 3 casos, se esperan 30
    assert "se esperan 30" in capsys.readouterr().out


def test_main_unknown_only_id(ev, no_openai, capsys):
    assert ev.main(["--golden", str(GOLDEN), "--only", "g01,g99"]) == 1
    assert "g99" in capsys.readouterr().out


def test_exit_code(ev):
    ok = {"error": None}
    ok = {"error": None, "judge_error": None}
    assert ev.exit_code([ok], None, judge=True) == 0
    assert ev.exit_code([ok, {**ok, "error": "DocsServerUnavailable"}], None, judge=True) == 1
    assert ev.exit_code([ok, {**ok, "judge_error": "JudgeError"}], None, judge=True) == 1
    assert ev.exit_code([ok, {**ok, "judge_error": "JudgeError"}], None, judge=False) == 0
    assert ev.exit_code([ok], "max_tokens", judge=True) == 2
    assert ev.exit_code([{**ok, "judge_error": "BudgetExceeded"}], "budget", judge=True) == 2
    assert ev.exit_code([{**ok, "error": "BudgetExceeded"}], "budget", judge=True) == 2
    assert ev.exit_code([ok], "crash:RuntimeError", judge=True) == 1


def test_main_happy_path_escribe_salidas(ev, seeded_corpus, tmp_path, monkeypatch, capsys):
    """`main` completo con fakes: valida, corre, escribe el json y el md e imprime el resumen; salida 0."""
    from docs_agent import api, config

    small = tmp_path / "small.json"
    small.write_text(json.dumps([c.model_dump() for c in golden_cases()]), encoding="utf-8")
    # Sin `.env`: ni la key real ni LangSmith; `DATABASE_URL` es la de tests (conftest) y el corpus el sembrado.
    test_settings = Settings(
        _env_file=None, openai_api_key="sk-test", fastapi_docs_ref="test-ref", top_k=5,
        no_answer_distance_threshold=0.52, chat_model="m",
    )
    monkeypatch.setattr(config, "get_settings", lambda: test_settings)
    monkeypatch.setattr(api, "make_openai", lambda wrapper=None: PerQuestionOpenAI())
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path / "results")

    async def fake_run(cases, settings, conn, client, judge, max_tokens, console, results):
        return await ev.run_cases(
            cases, settings, conn, client, QuestionTools(), judge, max_tokens, console, results=results
        )

    monkeypatch.setattr(ev, "_run", fake_run)
    assert ev.main(["--golden", str(small), "--only", "g01,g02,g03"]) == 0
    names = sorted(p.name for p in (tmp_path / "results").iterdir())
    md_path = next(p for p in (tmp_path / "results").iterdir() if p.suffix == ".md")
    md = md_path.read_text(encoding="utf-8")
    assert "Solo los casos: g01, g02, g03" in md
    assert "el costo del juez usa las tarifas de `m`" in md
    assert len(names) == 2 and not any("judge-review" in n for n in names)
    out = capsys.readouterr().out
    assert "Exactitud de ruta" in out and "3 casos (3 sin error · 0 errores)" in out
    assert "costo del juez" in out  # chat_model "m" ≠ JUDGE_MODEL: aviso de tarifas
    assert "sk-test" not in out
    assert "tracing LangSmith: apagado" in out


def test_main_crash_escribe_parciales(ev, seeded_corpus, tmp_path, monkeypatch, capsys):
    """Un error inesperado a mitad de corrida: se guardan los parciales con `aborted="crash:<Tipo>"` y sale 1."""
    from docs_agent import api, config

    small = tmp_path / "small.json"
    small.write_text(json.dumps([c.model_dump() for c in golden_cases()]), encoding="utf-8")
    test_settings = Settings(
        _env_file=None, openai_api_key="sk-test", fastapi_docs_ref="test-ref", top_k=5,
        no_answer_distance_threshold=0.52, chat_model="gpt-4.1-mini",
    )
    monkeypatch.setattr(config, "get_settings", lambda: test_settings)
    monkeypatch.setattr(api, "make_openai", lambda wrapper=None: PerQuestionOpenAI())
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path / "results")

    async def fake_run(cases, settings, conn, client, judge, max_tokens, console, results):
        tools = QuestionTools(raises={Q_OUT: RuntimeError("secreto-no-imprimir")})
        return await ev.run_cases(cases, settings, conn, client, tools, judge, max_tokens, console, results=results)

    monkeypatch.setattr(ev, "_run", fake_run)
    assert ev.main(["--golden", str(small), "--only", "g01,g02,g03"]) == 1
    data = json.loads(next((tmp_path / "results").glob("*.json")).read_text(encoding="utf-8"))
    assert data["run"]["aborted"] == "crash:RuntimeError"
    assert [c["id"] for c in data["cases"]] == ["g01", "g02"]
    assert data["run"]["tokens_total"] > 0
    assert len(list((tmp_path / "results").iterdir())) == 2
    out = capsys.readouterr().out
    assert "RuntimeError" in out and "secreto-no-imprimir" not in out
    assert "costo del juez" not in out  # mismo modelo: sin aviso
