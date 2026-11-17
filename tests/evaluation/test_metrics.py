"""Tests de las métricas puras de evaluación."""

import pytest

from docs_agent.evaluation.metrics import (
    compute_metrics,
    normalize_url,
    percentile,
    simulate_route,
    threshold_sweep,
    url_matches,
)


def case(**kw):
    base = {
        "id": "c", "question": "q", "lang": "es", "category": "in_basic",
        "expected_route": "answer", "expected_urls": ["https://x.com/a"],
        "route": "answer", "reason": None, "best_distance": 0.4,
        "retrieved_urls": [], "citations": ["https://x.com/a"], "answer": "r",
        "grounded": True, "latency_ms": 100.0, "cost_usd": 0.01, "judge": None,
        "judge_context": None, "judge_cost_usd": 0.0, "judge_error": None,
        "error": None,
    }
    base.update(kw)
    return base


def test_normalize_url():
    assert (
        normalize_url("http://FastAPI.tiangolo.com/tutorial/cors/")
        == "https://fastapi.tiangolo.com/tutorial/cors"
    )
    assert normalize_url("https://x.com/a/#b") == "https://x.com/a#b"
    assert normalize_url("https://x.com/") == "https://x.com"
    assert normalize_url("https://x.com/Path/A") == "https://x.com/Path/A"


def test_url_matches():
    assert url_matches("https://x.com/a#b", "https://x.com/a") is True
    assert url_matches("https://x.com/a#c", "https://x.com/a#b") is False
    assert url_matches("http://X.com/a/#b", "https://x.com/a#b") is True
    assert url_matches("https://x.com/ab", "https://x.com/a") is False
    assert url_matches("https://x.com/a", "https://x.com/a#b") is False


def test_percentile():
    assert percentile([100, 200, 300, 400], 50) == 250
    assert percentile([100, 200, 300, 400], 95) == pytest.approx(385)
    assert percentile([400, 100], 0) == 100
    assert percentile([7], 95) == 7
    assert percentile([], 50) is None


def test_compute_metrics_confusion_y_ruta():
    cases = [
        case(id="ok"),
        case(id="fns", route="no_se", reason="insufficient_context", citations=[]),
        case(id="fa", expected_route="no_se", expected_urls=[], category="out_near"),
        case(id="nok", expected_route="no_se", expected_urls=[], route="no_se",
             reason="out_of_domain", category="out_obvious", citations=[]),
    ]
    m = compute_metrics(cases)
    assert m["n"] == 4 and m["n_errors"] == 0
    assert m["route_accuracy"] == {"num": 2, "den": 4}
    assert m["confusion"] == {
        "answer_ok": 1, "false_no_se": 1, "false_answer": 1, "no_se_ok": 1,
    }
    # den: solo esperada=obtenida=answer (el primero)
    assert m["source_hit_any"] == {"num": 1, "den": 1}
    # grounded: casos con ruta obtenida answer (ok y fa)
    assert m["grounded_rate"] == {"num": 2, "den": 2}
    assert m["latency_p50_ms"] == 100.0
    assert m["cost_total_usd"] == pytest.approx(0.04)
    assert m["cost_per_question_usd"] == pytest.approx(0.01)


def test_in_multi_parcial():
    c = case(
        category="in_multi",
        expected_urls=["https://x.com/a", "https://x.com/b"],
        citations=["https://x.com/a#z"],
    )
    m = compute_metrics([c])
    assert m["source_hit_any"] == {"num": 1, "den": 1}
    assert m["source_hit_all_multi"] == {"num": 0, "den": 1}
    c2 = case(
        category="in_multi",
        expected_urls=["https://x.com/a", "https://x.com/b"],
        citations=["https://x.com/a", "https://x.com/b"],
    )
    assert compute_metrics([c2])["source_hit_all_multi"] == {"num": 1, "den": 1}


def test_errores_fuera_de_denominadores():
    m = compute_metrics([case(), case(id="e", route=None, error="boom", cost_usd=9.0)])
    assert m["n_errors"] == 1
    assert m["n"] == 1
    assert m["route_accuracy"] == {"num": 1, "den": 1}
    assert m["cost_total_usd"] == pytest.approx(0.01)


def test_faithfulness_y_costo_juez():
    j = {"score": 0.5, "unsupported_claims": [], "reason": ""}
    m = compute_metrics([
        case(judge=j, judge_cost_usd=0.002),
        case(judge={**j, "score": 1.0}, judge_cost_usd=0.002),
        case(judge=None),
    ])
    assert m["faithfulness_mean"] == pytest.approx(0.75)
    assert m["judge_cost_usd"] == pytest.approx(0.004)
    assert m["cost_total_usd"] == pytest.approx(0.034)
    assert compute_metrics([case()])["faithfulness_mean"] is None


def test_threshold_sweep():
    cls = case(id="cls", route="no_se", reason="out_of_domain", best_distance=0.7,
               expected_route="no_se", expected_urls=[])
    mid = case(id="mid", best_distance=0.51)
    none = case(id="none", best_distance=None, route="no_se",
                reason="insufficient_context")
    assert simulate_route(mid, 0.52) == "answer"
    assert simulate_route(mid, 0.50) == "no_se"
    assert simulate_route(cls, 0.99) == "no_se"
    assert simulate_route(none, 0.99) == "no_se"
    rows = {r["threshold"]: r for r in threshold_sweep([cls, mid, none])}
    assert set(rows) == {0.48, 0.50, 0.52, 0.55}
    for r in rows.values():
        assert r["cut_by_classifier"] == 1
        assert r["false_no_se_classifier"] == 0
    assert rows[0.48]["false_no_se_threshold"] == 2  # mid y none (esperadas answer)
    assert rows[0.52]["false_no_se_threshold"] == 1  # solo none
    assert rows[0.52]["cut_by_threshold"] == 1
    assert rows[0.48]["cut_by_threshold"] == 2
    assert rows[0.55]["route_accuracy"] == {"num": 2, "den": 3}


def test_sweep_clasificador_corta_esperada_answer_y_falso_answer():
    cls = case(id="cls", route="no_se", reason="out_of_domain", best_distance=0.7)
    fa = case(id="fa", expected_route="no_se", expected_urls=[], best_distance=0.3)
    err = case(id="e", route=None, error="x")
    r = threshold_sweep([cls, fa, err], thresholds=(0.5,))[0]
    assert r["false_no_se_classifier"] == 1
    assert r["false_answer"] == 1
    assert r["route_accuracy"] == {"num": 0, "den": 2}


def either(**kw):
    return case(expected_route="either", **kw)


def test_either_en_compute_metrics():
    m = compute_metrics([
        either(id="e1", route="no_se", reason="insufficient_context", citations=[]),
        either(id="e2"),  # answer citando esperada
        either(id="e3", citations=["https://x.com/otra"]),  # answer sin esperada
    ])
    assert m["confusion"] == {
        "answer_ok": 1, "false_no_se": 0, "false_answer": 1, "no_se_ok": 1,
    }
    assert m["route_accuracy"] == {"num": 2, "den": 3}
    # answered "either" entra a source hit y grounded
    assert m["source_hit_any"] == {"num": 1, "den": 2}
    assert m["grounded_rate"] == {"num": 2, "den": 2}


def test_either_en_threshold_sweep():
    a = either(id="a", best_distance=0.9)  # simulada no_se por umbral
    b = either(id="b", best_distance=0.1)  # simulada answer
    c = either(id="c", route="no_se", reason="out_of_domain", best_distance=0.7)
    for r in threshold_sweep([a, b, c]):
        assert r["false_no_se_threshold"] == 0
        assert r["false_no_se_classifier"] == 0
        assert r["false_answer"] == 0
        assert r["route_accuracy"] == {"num": 3, "den": 3}


def test_unsupported_any_rate():
    j_ok = {"score": 1.0, "unsupported_claims": [], "reason": ""}
    j_bad = {"score": 0.5, "unsupported_claims": ["inventada"], "reason": ""}
    m = compute_metrics([
        case(judge=j_ok),
        case(judge=j_bad),
        case(judge=None),  # sin juicio: fuera del denominador
        case(expected_route="no_se", expected_urls=[], route="no_se", citations=[], judge=None),
        case(judge=j_bad, error="DocsServerUnavailable"),  # con error: fuera de todo
    ])
    assert m["unsupported_any_rate"] == {"num": 1, "den": 2}
    assert compute_metrics([case()])["unsupported_any_rate"] == {"num": 0, "den": 0}


def test_faithfulness_n():
    j = {"score": 0.5, "unsupported_claims": [], "reason": ""}
    m = compute_metrics([
        case(judge=j),
        case(judge=None, judge_error="JudgeError"),
        case(expected_route="no_se", expected_urls=[], route="no_se", citations=[], judge=None),
    ])
    assert m["faithfulness_n"] == {"num": 1, "den": 2}  # juzgadas / respondidas
