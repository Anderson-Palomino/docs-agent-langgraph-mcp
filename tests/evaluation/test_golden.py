"""Golden set (`docs_agent.evaluation.golden`): validación de casos, unicidad de ids y distribución del spec 5.1."""

import importlib.util
import json
from pathlib import Path

import pytest

from docs_agent.evaluation.golden import GoldenSetError, check_distribution, load_golden

ROOT = Path(__file__).resolve().parents[2]
URL = "https://fastapi.tiangolo.com/tutorial/body/"


def _case(i: int, category: str, lang: str = "es", judge: bool = False, **overrides) -> dict:
    if category.startswith("in_") or category == "trap_ambiguous":
        route = "answer"
    elif category == "trap_missing_fact":
        route = "either"
    else:
        route = "no_se"
    case = {
        "id": f"g{i:02d}",
        "question": f"pregunta {i}",
        "lang": lang,
        "category": category,
        "expected_route": route,
        "expected_urls": [] if route == "no_se" else [URL],
        "notes": "caso sintético",
        "judge_review": judge,
    }
    case.update(overrides)
    return case


def _valid_set() -> list[dict]:
    """30 casos que cumplen la distribución: 18 dentro (9/9, 2 multi), 8 fuera, 4 trampa, 6 para el juez (uno `either`)."""
    cats = ["in_basic"] * 8 + ["in_intermediate"] * 8 + ["in_multi"] * 2
    langs = ["es", "en"] * 9
    cases = [_case(i + 1, c, l, judge=i < 5) for i, (c, l) in enumerate(zip(cats, langs))]
    outs = ["out_obvious"] * 2 + ["out_near"] * 6
    cases += [_case(19 + i, c) for i, c in enumerate(outs)]
    traps = ["trap_mentioned", "trap_mentioned", "trap_ambiguous", "trap_missing_fact"]
    cases += [_case(27 + i, c, judge=c == "trap_missing_fact") for i, c in enumerate(traps)]
    return cases


def _write(tmp_path: Path, cases: list[dict]) -> Path:
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_valid_set(tmp_path):
    cases = load_golden(_write(tmp_path, _valid_set()))
    assert len(cases) == 30
    assert cases[0].id == "g01" and cases[0].expected_urls == [URL]


def test_load_rejects_duplicate_ids(tmp_path):
    cases = _valid_set()
    cases[1]["id"] = "g01"
    with pytest.raises(GoldenSetError, match="g01"):
        load_golden(_write(tmp_path, cases))


def test_answer_requires_urls(tmp_path):
    cases = _valid_set()
    cases[0]["expected_urls"] = []
    with pytest.raises(GoldenSetError, match="g01"):
        load_golden(_write(tmp_path, cases))


def test_no_se_requires_empty_urls(tmp_path):
    cases = _valid_set()
    cases[18]["expected_urls"] = [URL]
    with pytest.raises(GoldenSetError, match="g19"):
        load_golden(_write(tmp_path, cases))


def test_judge_review_only_on_answer(tmp_path):
    cases = _valid_set()
    cases[18]["judge_review"] = True
    with pytest.raises(GoldenSetError, match="g19"):
        load_golden(_write(tmp_path, cases))


def test_either_requires_urls(tmp_path):
    cases = _valid_set()
    cases[29]["expected_urls"] = []
    with pytest.raises(GoldenSetError, match="g30"):
        load_golden(_write(tmp_path, cases))


def test_judge_review_allowed_on_either(tmp_path):
    case = load_golden(_write(tmp_path, _valid_set()))[29]
    assert case.expected_route == "either" and case.judge_review is True


def test_load_rejects_unknown_category(tmp_path):
    cases = _valid_set()
    cases[0]["category"] = "in_hard"
    with pytest.raises(GoldenSetError, match="g01"):
        load_golden(_write(tmp_path, cases))


def test_load_rejects_non_list_and_bad_json(tmp_path):
    with pytest.raises(GoldenSetError):
        load_golden(_write(tmp_path, {"id": "g01"}))
    bad = tmp_path / "bad.json"
    bad.write_text("[{", encoding="utf-8")
    with pytest.raises(GoldenSetError):
        load_golden(bad)


def test_check_distribution_ok(tmp_path):
    assert check_distribution(load_golden(_write(tmp_path, _valid_set()))) == []


def test_check_distribution_reports_missing(tmp_path):
    cases = _valid_set()
    cases[0] = _case(1, "out_near")  # 17 dentro, 9 fuera, y un caso del juez menos
    problems = check_distribution(load_golden(_write(tmp_path, cases)))
    text = " | ".join(problems)
    assert "in_corpus" in text
    assert "out" in text
    assert "judge_review" in text


def test_check_distribution_reports_lang_multi_and_trap_types(tmp_path):
    cases = _valid_set()
    cases[16]["category"] = "in_basic"  # queda 1 in_multi
    cases[1]["lang"] = "es"  # 10 es / 8 en dentro
    cases[28] = _case(29, "trap_mentioned")  # sin trap_ambiguous
    text = " | ".join(check_distribution(load_golden(_write(tmp_path, cases))))
    assert "in_multi" in text
    assert "in_corpus es: 10 casos" in text
    assert "in_corpus en: 8 casos" in text
    assert "trap_ambiguous" in text


@pytest.fixture(scope="module")
def demo_moments() -> dict[int, str]:
    spec = importlib.util.spec_from_file_location("demo_check", ROOT / "scripts" / "demo_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MOMENTS


def test_real_golden_set_is_valid(demo_moments):
    cases = load_golden(ROOT / "eval" / "golden_set.json")
    assert check_distribution(cases) == []
    assert [c.id for c in cases] == [f"g{i:02d}" for i in range(1, 31)]
    questions = {c.question for c in cases}
    assert demo_moments[2] in questions
    assert demo_moments[3] in questions
    assert demo_moments[1] not in questions
    by_id = {c.id: c for c in cases}
    assert by_id["g01"].expected_urls == ["https://fastapi.tiangolo.com/tutorial/security/get-current-user/"]
    g30 = by_id["g30"]
    assert g30.expected_route == "either" and g30.judge_review
    assert g30.expected_urls == ["https://fastapi.tiangolo.com/deployment/versions/"]


@pytest.fixture(scope="module")
def review():
    spec = importlib.util.spec_from_file_location("golden_review", ROOT / "scripts" / "golden_review.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_url_exists_rules(review):
    known = {"https://fastapi.tiangolo.com/advanced/websockets/#create-a-websocket", "https://fastapi.tiangolo.com/tutorial/body/"}
    assert review.url_exists("https://fastapi.tiangolo.com/tutorial/body/", known)
    assert review.url_exists("https://fastapi.tiangolo.com/advanced/websockets/", known)  # sin ancla: cualquier sección
    assert review.url_exists("https://fastapi.tiangolo.com/advanced/websockets/#create-a-websocket", known)
    assert not review.url_exists("https://fastapi.tiangolo.com/advanced/websockets/#otra", known)  # con ancla: exacta
    assert not review.url_exists("https://fastapi.tiangolo.com/advanced/web", known)  # no es prefijo de página


def test_review_render_marks_missing_and_leaves_owner_column_empty(review, tmp_path):
    cases = load_golden(_write(tmp_path, _valid_set()))
    cases[0] = cases[0].model_copy(update={"question": "a | b", "expected_urls": ["https://x.test/nope/"]})
    md = review.render_review(cases, {URL}, ["in_multi: 1 casos"])
    rows = [line for line in md.splitlines() if line.startswith("| g")]
    assert len(rows) == 30
    assert "a \| b" in rows[0] and "| ✗ |" in rows[0]
    assert "| ✓ |" in rows[1] and rows[1].endswith("|  |")
    assert "| no_se | — | — |" in rows[18]
    assert "in_multi: 1 casos" in md
    header, separator = md.splitlines()[7:9]
    assert header.count("|") == separator.count("|") == len(review.COLUMNS) + 1


def test_review_settings_error_prints_only_type(review, monkeypatch, capsys):
    from pydantic import BaseModel, ValidationError

    class _Fake(BaseModel):
        database_url: int

    try:
        _Fake(database_url="postgresql://secreto@host/db")
    except ValidationError as exc:
        error = exc

    def _boom():
        raise error

    monkeypatch.setattr(review, "get_settings", _boom)
    assert review.main([]) == 1
    err = capsys.readouterr().err
    assert "ValidationError" in err
    assert "secreto" not in err
