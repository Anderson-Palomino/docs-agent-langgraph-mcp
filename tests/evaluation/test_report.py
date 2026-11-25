"""Tests del reporte de la evaluación (Markdown y revisión del juez), sin red ni base de datos."""

from datetime import date

from docs_agent.evaluation.golden import GoldenCase
from docs_agent.evaluation.metrics import compute_metrics, threshold_sweep
from docs_agent.evaluation.report import (
    REVIEW_TEXT_MAX_CHARS,
    TRUNCATION_MARK,
    parse_review,
    render_judge_review,
    render_markdown,
    results_path,
    review_case_ids,
    score_review,
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


# --- render_judge_review (hoja sí/no) ---

HEADER = "| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |"


def test_hoja_tabla_de_afirmaciones_y_contexto():
    md = render_judge_review([result("g01")], [golden("g01", True)], [])
    assert "## g01" in md
    assert HEADER in md
    assert "| 1 | apoyada | apoyada | | |" in md
    assert "| 2 | inventada | no apoyada | | |" in md
    assert "respuesta completa g01" in md
    assert "SECCION g01" in md and "FRAGMENTO g01" in md and A in md and B in md
    assert "<details>" in md and "````text" in md
    # el formato viejo (puntaje 0-1) ya no existe
    assert "Puntaje del dueño" not in md and "0-1" not in md and "✓" not in md


def test_hoja_extracto_y_texto_completo_en_details():
    long_text = "x" * (REVIEW_TEXT_MAX_CHARS + 500)
    case = result("g01", judge_context=f"[1] Request Body\nURL: {A}\n{long_text}")
    case["context_parts"] = case["context_parts"][:1]
    md = render_judge_review([case], [golden("g01", True)], [])
    assert TRUNCATION_MARK in md
    assert md.count(long_text) == 1  # completo solo dentro del <details>
    assert long_text in md[md.index("<details>") :]
    assert "x" * (REVIEW_TEXT_MAX_CHARS + 1) not in md[: md.index("<details>")]


def test_hoja_marcados_en_orden_y_extras_solo_si_responden():
    gold = [golden("g01", True), golden("g02", False), golden("g03", False), golden("g06", False), golden("g10", True)]
    no_se = result(
        "g06", route="no_se", reason="insufficient_context", citations=[], judge=None, judge_context=None,
        context_parts=[],
    )
    cases = [result("g01"), result("g02"), result("g03"), no_se, result("g10")]
    md = render_judge_review(cases, gold, ["g03", "g06"])
    heads = [line for line in md.splitlines() if line.startswith("## ")]
    assert [h.split()[1] for h in heads] == ["g01", "g10", "g03"]
    assert "## g02" not in md and "## g06" not in md
    assert review_case_ids(cases, gold, ["g03", "g06"]) == ["g01", "g10", "g03"]


def test_hoja_marcado_sin_respuesta_lleva_nota_y_sin_tabla():
    gold = [golden("g30", True, route="either"), golden("g31", True)]
    no_se = result(
        "g30", route="no_se", reason="insufficient_context", citations=[], judge=None,
        judge_context=None, context_parts=[], expected_route="either",
    )
    md = render_judge_review([no_se], gold, [])
    assert "## g30" in md and "## g31" in md
    assert md.count("no se respondió en esta corrida") == 2
    assert HEADER not in md


def test_hoja_escapa_barras_en_afirmaciones():
    case = result("g01")
    case["judge"]["claims"] = [{"text": "usa a | b\ny c", "supported": True}]
    md = render_judge_review([case], [golden("g01", True)], [])
    assert "| 1 | usa a \\| b y c | apoyada | | |" in md


# --- parse_review / score_review ---


def filled(rows: list[tuple[str, int, str]]) -> str:
    out = []
    for cid, n, agree in rows:
        out += [f"## {cid} — pregunta", "", "### Afirmaciones del juez", "", HEADER, "|---|---|---|---|---|", f"| {n} | texto | apoyada | {agree} | nota |", ""]
    return "\n".join(out)


def test_parse_review_variantes_de_si_no():
    md = filled(
        [("g01", 1, "sí"), ("g01", 2, "Si"), ("g01", 3, " NO "), ("g01", 4, "SÍ"), ("g01", 5, ""), ("g01", 6, "tal vez")]
    )
    rows = parse_review(md)
    assert [r["agree"] for r in rows] == [True, True, False, True, None, None]
    assert [r["n"] for r in rows] == [1, 2, 3, 4, 5, 6]
    assert {r["case_id"] for r in rows} == {"g01"}


def test_parse_review_con_hoja_generada_ignora_el_contexto():
    ctx = f"[1] Request Body\nURL: {A}\n## titulo falso\n| 1 | x | y | sí | z |\n```py\nx\n```\n"
    case = result("g01", judge_context=ctx)
    case["context_parts"] = case["context_parts"][:1]
    md = render_judge_review([case], [golden("g01", True)], [])
    rows = parse_review(md)
    assert [(r["case_id"], r["n"], r["agree"]) for r in rows] == [("g01", 1, None), ("g01", 2, None)]
    md = md.replace("| 1 | apoyada | apoyada | | |", "| 1 | apoyada | apoyada | sí | ok |")
    assert [r["agree"] for r in parse_review(md)] == [True, None]


def test_parse_review_ignora_titulos_y_tablas_de_la_respuesta():
    case = result("g01", answer="## Intro — x\n\n| 1 | a | b | sí | c |\n\ntexto")
    rows = parse_review(render_judge_review([case], [golden("g01", True)], []))
    assert [(r["case_id"], r["n"], r["agree"]) for r in rows] == [("g01", 1, None), ("g01", 2, None)]


def sheet_with(*lines: str) -> str:
    return "\n".join(["## g01 — pregunta", "", "### Afirmaciones del juez", "", HEADER, "|---|---|---|---|---|", *lines, ""])


def test_parse_review_acepta_fila_sin_barra_final_ni_nota():
    rows = parse_review(sheet_with("| 1 | a | apoyada | sí", "| 2 | b | no apoyada | no |", "| 3 | c | apoyada | Si | nota"))
    assert [(r["n"], r["agree"], r["problem"]) for r in rows] == [(1, True, None), (2, False, None), (3, True, None)]


def test_parse_review_fila_ilegible_se_reporta_y_cuenta():
    rows = parse_review(sheet_with("| 1 | a | apoyada | sí | |", "| 2 texto roto", "| 3 | c | apoyada | no | |"))
    assert [r["n"] for r in rows] == [1, 2, 3]
    assert rows[1]["agree"] is None and rows[1]["problem"] == "fila ilegible"
    s = score_review(rows)
    assert s["claims_total"] == 3 and s["claims_answered"] == 2


def test_parse_review_valor_no_reconocido_y_vacio_se_distinguen():
    rows = parse_review(sheet_with("| 1 | a | apoyada | sí. | |", "| 2 | b | apoyada | sí, pero | |", "| 3 | c | apoyada | | |"))
    assert [(r["agree"], r["problem"], r["raw"]) for r in rows] == [
        (None, "valor no reconocido", "sí."),
        (None, "valor no reconocido", "sí, pero"),
        (None, "sin responder", ""),
    ]


def test_score_review_cuenta_y_casos():
    rows = [
        {"case_id": "g01", "n": 1, "agree": True},
        {"case_id": "g01", "n": 2, "agree": True},
        {"case_id": "g02", "n": 1, "agree": True},
        {"case_id": "g02", "n": 2, "agree": False},
        {"case_id": "g03", "n": 1, "agree": True},
        {"case_id": "g03", "n": 2, "agree": None},  # le falta una: no está de acuerdo
        {"case_id": "g04", "n": 1, "agree": None},
    ]
    assert score_review(rows) == {
        "claims_answered": 5, "claims_total": 7, "claims_agree": 4,
        "case_agree": 1, "cases_answered": 2, "cases_total": 4,
    }


def test_score_review_sin_respuestas_no_divide_por_cero():
    assert score_review([]) == {
        "claims_answered": 0, "claims_total": 0, "claims_agree": 0,
        "case_agree": 0, "cases_answered": 0, "cases_total": 0,
    }
    s = score_review(parse_review(filled([("g01", 1, "")])))
    assert s["claims_total"] == 1 and s["claims_answered"] == 0 and s["case_agree"] == 0


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
