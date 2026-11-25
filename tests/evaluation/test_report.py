"""Tests del reporte de la evaluación (Markdown y revisión del juez), sin red ni base de datos."""

from datetime import date

from docs_agent.evaluation.golden import GoldenCase
from docs_agent.evaluation.metrics import compute_metrics, threshold_sweep
from docs_agent.evaluation.report import (
    REVIEW_TEXT_MAX_CHARS,
    TRUNCATION_MARK,
    render_judge_review,
    render_markdown,
    results_path,
)

A = "https://fastapi.tiangolo.com/tutorial/body/"
B = "https://fastapi.tiangolo.com/tutorial/query-params/"


def golden(cid: str, judge_review: bool, route: str = "answer") -> GoldenCase:
    return GoldenCase(
        id=cid,
        question=f"pregunta {cid}",
        lang="es",
        category="in_basic" if route != "no_se" else "out_obvious",
        expected_route=route,
        expected_urls=[A] if route != "no_se" else [],
        notes="",
        judge_review=judge_review,
    )


def result(cid: str, **kw) -> dict:
    context = f"[1] Request Body\nURL: {A}\nSECCION {cid}\n\n[2] Query Parameters\nURL: {B}\nFRAGMENTO {cid}"
    base = {
        "id": cid, "question": f"pregunta {cid}", "lang": "es", "category": "in_basic",
        "expected_route": "answer", "expected_urls": [A], "route": "answer", "reason": None,
        "is_fastapi": True, "best_distance": 0.3, "retrieved_urls": [A, B], "citations": [A],
        "grounded": True, "answer": f"respuesta completa {cid}", "tools_used": ["search_docs", "get_section"],
        "usage": {}, "tokens": 500, "cost_usd": 0.001, "latency_ms": 1200.0,
        "judge_context": context,
        "context_parts": [
            {"n": 1, "title": "Request Body", "url": A, "section": True},
            {"n": 2, "title": "Query Parameters", "url": B, "section": False},
        ],
        "judge": {
            "score": 0.5,
            "unsupported_claims": ["inventada"],
            "reason": "una afirmación sin apoyo",
            "claims": [{"text": "apoyada", "supported": True}, {"text": "inventada", "supported": False}],
        },
        "judge_tokens": 120, "judge_cost_usd": 0.0001, "judge_error": None, "error": None,
    }
    base.update(kw)
    return base


def run_info(**kw) -> dict:
    base = {
        "date": "2026-11-18", "chat_model": "gpt-4.1-mini", "judge_model": "gpt-4.1-mini", "judge": True,
        "threshold": 0.52, "top_k": 5, "docs_ref": "0.162.0", "golden": "eval/golden_set.json",
        "max_tokens": 400_000, "aborted": None, "tokens_total": 1234, "cost_total_usd_all": 0.0123,
    }
    base.update(kw)
    return base


# --- results_path ---


def test_results_path_no_pisa(tmp_path):
    day = date(2026, 11, 18)
    assert results_path(tmp_path, day) == tmp_path / "2026-11-18.json"
    (tmp_path / "2026-11-18.json").write_text("{}", encoding="utf-8")
    assert results_path(tmp_path, day) == tmp_path / "2026-11-18-2.json"
    (tmp_path / "2026-11-18-2.json").write_text("{}", encoding="utf-8")
    assert results_path(tmp_path, day) == tmp_path / "2026-11-18-3.json"
    assert results_path(tmp_path, day, ".md") == tmp_path / "2026-11-18.md"


def test_results_path_with_label_does_not_overwrite(tmp_path):
    day = date(2026, 11, 24)
    assert results_path(tmp_path, day, label="holdout") == tmp_path / "2026-11-24-holdout.json"
    (tmp_path / "2026-11-24-holdout.json").write_text("{}", encoding="utf-8")
    assert results_path(tmp_path, day, label="holdout") == tmp_path / "2026-11-24-holdout-2.json"
    assert results_path(tmp_path, day) == tmp_path / "2026-11-24.json"


# --- render_markdown ---


def test_render_markdown_metricas_y_umbrales():
    cases = [result("g01"), result("g02", error="DocsServerUnavailable")]
    md = render_markdown(run_info(), compute_metrics(cases), threshold_sweep(cases))
    for label in (
        "Exactitud de ruta",
        "Acierto de fuente",
        "Citas válidas",
        "Fidelidad",
        "Respuestas con alguna afirmación no apoyada",
        "p50",
        "p95",
        "Costo",
    ):
        assert label in md, label
    assert "| Casos | 2 casos (1 sin error · 1 error) |" in md
    assert "| Fidelidad (media del juez) | 0.50 (1 juzgada / 1 respondida) |" in md
    assert "| Exactitud de ruta | 100.0% (1/1) |" in md
    assert "| Respuestas con alguna afirmación no apoyada | 100.0% (1/1) |" in md
    assert "| Costo total de la corrida (todos los casos) | 0.0123 USD |" in md  # incluye los casos con error
    for t in ("0.48", "0.50", "0.52", "0.55"):
        assert f"| {t}" in md, t
    assert "0.52 (actual)" in md


def test_render_markdown_sin_denominador_y_abortada():
    md = render_markdown(run_info(aborted="max_tokens"), compute_metrics([]), threshold_sweep([]))
    assert "—" in md
    assert "max_tokens" in md


# --- render_judge_review ---


def test_render_judge_review_solo_casos_judge_review():
    gold = [golden("g01", True), golden("g02", False), golden("g03", True)]
    cases = [result("g01"), result("g02"), result("g03")]
    md = render_judge_review(cases, gold)
    assert "## g01" in md and "## g03" in md
    assert "## g02" not in md
    assert md.count("Puntaje del dueño (0-1): ___ · Comentario: ___") == 2
    # fragmentos que vio el modelo, con URL y texto
    assert "SECCION g01" in md and "FRAGMENTO g01" in md and A in md and B in md
    assert "respuesta completa g01" in md
    assert "````text" in md  # cerca de 4: un bloque ``` de la doc no rompe el fragmento
    assert "0.50" in md
    assert "✓ apoyada" in md and "✗ inventada" in md
    assert "una afirmación sin apoyo" in md


def test_render_judge_review_trunca_textos_largos():
    long_text = "x" * (REVIEW_TEXT_MAX_CHARS + 500)
    case = result("g01", judge_context=f"[1] Request Body\nURL: {A}\n{long_text}")
    case["context_parts"] = case["context_parts"][:1]
    md = render_judge_review([case], [golden("g01", True)])
    assert TRUNCATION_MARK in md
    assert "x" * (REVIEW_TEXT_MAX_CHARS + 1) not in md


def test_render_judge_review_no_se_y_no_corrido():
    gold = [golden("g30", True, route="either"), golden("g31", True)]
    no_se = result(
        "g30", route="no_se", reason="insufficient_context", citations=[], judge=None,
        judge_context=None, context_parts=[], expected_route="either",
    )
    md = render_judge_review([no_se], gold)
    assert "no_se" in md and "no hay respuesta que juzgar" in md
    assert "g31" in md and "no se corrió" in md
    assert md.count("Puntaje del dueño (0-1): ___ · Comentario: ___") == 2


def test_casos_plural_y_only_lista():
    cases = [result("g01"), result("g02")]
    md = render_markdown(run_info(only=["g01", "g02"]), compute_metrics(cases), threshold_sweep(cases))
    assert "| Casos | 2 casos (2 sin error · 0 errores) |" in md
    assert "Solo los casos: g01, g02" in md
    assert "| Fidelidad (media del juez) | 0.50 (2 juzgadas / 2 respondidas) |" in md
    one = render_markdown(run_info(), compute_metrics([result("g01")]), [])
    assert "| Casos | 1 caso (1 sin error · 0 errores) |" in one


def test_render_markdown_crash():
    md = render_markdown(run_info(aborted="crash:OperationalError"), compute_metrics([]), [])
    assert "crash:OperationalError" in md
