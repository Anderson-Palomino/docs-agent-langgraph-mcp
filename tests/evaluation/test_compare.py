"""Tests de la comparación antes/después de dos corridas (spec 5.2), sin red ni base de datos."""

import importlib.util
import json
from pathlib import Path

from docs_agent.evaluation.compare import (
    case_detail,
    classifier_accuracy,
    classifier_flips,
    es_out_of_corpus_rows,
    render_comparison,
)

A = "https://fastapi.tiangolo.com/tutorial/body/"
ROOT = Path(__file__).resolve().parents[2]


def row(cid: str, **kw) -> dict:
    """Fila mínima como la de `evaluate.py` del 11-17 (sin `language`/`search_query`/`translated`)."""
    base = {
        "id": cid, "question": f"pregunta {cid}", "lang": "es", "category": "in_basic",
        "expected_route": "answer", "expected_urls": [A], "route": "answer", "reason": None,
        "is_fastapi": True, "best_distance": 0.4, "retrieved_urls": [A], "citations": [A],
        "grounded": True, "answer": "respuesta", "latency_ms": 1000.0, "cost_usd": 0.001,
        "judge_cost_usd": 0.0005, "judge": {"score": 1.0, "unsupported_claims": []}, "error": None,
    }
    base.update(kw)
    return base


def cut(cid: str, **kw) -> dict:
    """Fila cortada por el clasificador."""
    return row(cid, route="no_se", reason="out_of_domain", is_fastapi=False, citations=[],
               grounded=False, judge=None, judge_cost_usd=0.0, **kw)


def run(cases: list[dict], day: str = "2026-11-17") -> dict:
    return {"run": {"date": day, "chat_model": "gpt-4.1-mini", "threshold": 0.52}, "cases": cases}


# --- classifier_accuracy ---


def test_classifier_accuracy_cuenta_answer_y_no_se_del_clasificador():
    cases = [
        row("a1"),
        cut("a2"),  # answer cortado por el clasificador: error
        cut("n1", expected_route="no_se", category="out_obvious", expected_urls=[]),
        row("e1", expected_route="either", category="trap_missing_fact"),
    ]
    assert classifier_accuracy(cases) == {"num": 2, "den": 3}


def test_classifier_accuracy_excluye_no_se_que_le_toca_al_umbral_y_errores():
    cases = [
        row("a1"),
        # trap_missing_fact no_se: lo corta el umbral, no el clasificador → fuera del denominador
        row("t1", expected_route="no_se", category="trap_missing_fact", route="no_se",
            reason="insufficient_context", expected_urls=[]),
        cut("m1", expected_route="no_se", category="trap_mentioned", expected_urls=[]),
        row("x1", error="TimeoutError"),
    ]
    assert classifier_accuracy(cases) == {"num": 2, "den": 2}


# --- classifier_flips ---


def test_classifier_flips_solo_los_que_cambian():
    before = [cut("g03"), row("g01"), cut("g19", expected_route="no_se", category="out_obvious")]
    after = [row("g03", route="no_se", reason="insufficient_context"), row("g01"),
             cut("g19", expected_route="no_se", category="out_obvious")]
    assert classifier_flips(before, after) == [
        {"id": "g03", "expected_route": "answer", "before_cut": True, "after_cut": False}
    ]


# --- es_out_of_corpus_rows ---


def test_es_out_of_corpus_g25_cortada_por_clasificador_y_mas_cerca():
    before = [
        cut("g25", expected_route="no_se", category="out_near", best_distance=0.4073),
        cut("g20", lang="en", expected_route="no_se", category="out_obvious", best_distance=0.8),
        row("g30", expected_route="either", category="trap_missing_fact", best_distance=0.41),
    ]
    after = [
        cut("g25", expected_route="no_se", category="out_near", best_distance=0.35),
        cut("g20", lang="en", expected_route="no_se", category="out_obvious", best_distance=0.8),
        row("g30", expected_route="either", category="trap_missing_fact", route="no_se",
            reason="insufficient_context", best_distance=0.6),
    ]
    rows = es_out_of_corpus_rows(before, after)
    assert [r["id"] for r in rows] == ["g25", "g30"]
    g25 = rows[0]
    assert g25["cut_by_before"] == "classifier"
    assert g25["cut_by_after"] == "classifier"
    assert g25["distance_before"] == 0.4073
    assert g25["distance_after"] == 0.35
    assert g25["closer"] is True
    g30 = rows[1]
    assert g30["route_before"] == "answer" and g30["cut_by_before"] is None
    assert g30["route_after"] == "no_se" and g30["cut_by_after"] == "threshold"
    assert g30["closer"] is False


def test_es_out_of_corpus_sin_distancia_closer_none():
    before = [cut("g19", expected_route="no_se", category="out_obvious", best_distance=None)]
    after = [cut("g19", expected_route="no_se", category="out_obvious", best_distance=0.8)]
    assert es_out_of_corpus_rows(before, after)[0]["closer"] is None


# --- case_detail ---


def test_case_detail_filas_sin_claves_nuevas():
    before = [row("g03", route="no_se", reason="insufficient_context", best_distance=0.6033)]
    after = [row("g03", best_distance=0.41, search_query="how to declare a body", translated=True,
                 language="es", retrieved_urls=[A])]
    (d,) = case_detail(before, after, ["g03"])
    assert d == {
        "id": "g03", "question": "pregunta g03", "distance_before": 0.6033, "distance_after": 0.41,
        "route_before": "no_se", "route_after": "answer", "search_query_after": "how to declare a body",
        "retrieved_after": [A],
    }
    (old,) = case_detail(before, before, ["g03"])
    assert old["search_query_after"] is None


# --- render_comparison ---

ROW_NAMES = [
    "Ruta", "Ruta del clasificador", "Falsos «no sé»", "Falsos «respondí»", "Citas válidas",
    "Acierto de fuente", "Fidelidad", "Latencia p50", "Latencia p95",
    "Costo por pregunta (sin juez)", "Costo por pregunta (con juez)",
]


def _golden_like() -> list[dict]:
    return [
        row("g01"),
        row("g03", route="no_se", reason="insufficient_context", best_distance=0.6033),
        row("g06", route="no_se", reason="insufficient_context", best_distance=0.6165),
        row("g07", route="no_se", reason="insufficient_context", best_distance=0.5892),
        row("g09", route="no_se", reason="insufficient_context", best_distance=0.6666),
        cut("g25", expected_route="no_se", category="out_near", best_distance=0.4073),
    ]


def test_render_comparison_tabla_espanol_detalle_y_holdout():
    before = run(_golden_like())
    after = run(_golden_like(), day="2026-11-24")
    holdout = run([row("h01"), cut("h05", expected_route="no_se", category="out_near")], day="2026-11-24")
    md = render_comparison(before, after, holdout)
    lines = md.splitlines()
    for name in ROW_NAMES:
        assert any(line.startswith(f"| {name} |") for line in lines), name
    assert "## Español fuera del corpus" in md
    es_section = md.split("## Español fuera del corpus", 1)[1].split("\n## ", 1)[0]
    assert "g25" in es_section
    detail = md.split("## Detalle", 1)[1].split("\n## ", 1)[0]
    for cid in ("g03", "g06", "g07", "g09"):
        assert cid in detail
    assert "## Holdout (prompt congelado, una corrida)" in md
    main_table = md.split("## Holdout", 1)[0]
    assert "h01" not in main_table and "h05" not in main_table
    holdout_section = md.split("## Holdout (prompt congelado, una corrida)", 1)[1]
    assert "h05" in holdout_section
    # una línea dice qué cuenta la ruta del clasificador
    assert "trap_mentioned" in md


def test_render_comparison_sin_holdout_y_sin_claves_nuevas_muestra_raya():
    before = run(_golden_like())
    md = render_comparison(before, before, None)
    assert "Holdout" not in md
    detail = md.split("## Detalle", 1)[1].split("\n## ", 1)[0]
    g03_line = next(line for line in detail.splitlines() if line.startswith("| g03"))
    assert "—" in g03_line


def test_render_comparison_casos_faltantes_y_errores_no_rompen():
    before = run([row("g01"), row("g03", error="boom", route=None, best_distance=None)])
    after = run([row("g01")], day="2026-11-24")
    md = render_comparison(before, after, None)
    assert "| g03 |" in md or "g03" in md


# --- CLI ---


def test_cli_escribe_el_markdown(tmp_path):
    src = tmp_path / "antes.json"
    src.write_text(json.dumps(run(_golden_like())), encoding="utf-8")
    out = tmp_path / "x.md"
    spec = importlib.util.spec_from_file_location("compare_runs", ROOT / "scripts" / "compare_runs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main([str(src), str(src), "--out", str(out)]) == 0
    assert "Ruta del clasificador" in out.read_text(encoding="utf-8")
