"""Tests del juez de fidelidad (sin llamar a OpenAI)."""

import pytest
from pydantic import ValidationError

from docs_agent.agent.graph import SECTION_MAX_CHARS, SECTION_TRUNCATION_MARK
from docs_agent.evaluation.judge import JUDGE_MODEL, JudgeError, Judgment, judge_answer, judge_context
from tests.fakes import FakeOpenAI


def test_judge_answer_usa_modelo_temperatura_y_manda_todo():
    client = FakeOpenAI(judge_claims=[("a", True), ("b", True), ("c", True), ("d", False)])
    j, pt, ct = judge_answer(client, "¿Cómo?", "CTX-UNICO", "RESP-UNICA")
    call = client.calls[0]
    assert call["model"] == JUDGE_MODEL == "gpt-4.1-mini"
    assert call["temperature"] == 0
    text = " ".join(m["content"] for m in call["messages"])
    assert "¿Cómo?" in text and "CTX-UNICO" in text and "RESP-UNICA" in text
    assert isinstance(j, Judgment) and j.score == 0.75
    assert (pt, ct) == (100, 20)


def test_judge_answer_rechazo_lanza_judge_error():
    with pytest.raises(JudgeError):
        judge_answer(FakeOpenAI(judge_refusal=True), "q", "c", "a")


def test_judgment_valida_rango():
    with pytest.raises(ValidationError):
        Judgment(score=1.2, unsupported_claims=[], reason="x")
    with pytest.raises(ValidationError):
        Judgment(score=-0.1, unsupported_claims=[], reason="x")


def _results():
    return [
        {"url": "https://x.com/a", "title": "A", "content": "contenido-a", "distance": 0.3},
        {"url": "https://x.com/b", "title": "B", "content": "contenido-b", "distance": 0.4},
    ]


def test_judge_context_fragmentos_con_url():
    ctx = judge_context({"results": _results(), "section": None})
    for s in ("https://x.com/a", "contenido-a", "https://x.com/b", "contenido-b"):
        assert s in ctx


def test_judge_context_seccion_reemplaza_primer_fragmento_y_trunca():
    long = "z" * (SECTION_MAX_CHARS + 500)
    ctx = judge_context({"results": _results(), "section": {"content": long}})
    assert "contenido-a" not in ctx  # como el modelo: [1] lleva la sección, no el fragmento
    assert "contenido-b" in ctx
    assert "z" * SECTION_MAX_CHARS + SECTION_TRUNCATION_MARK in ctx
    assert "z" * (SECTION_MAX_CHARS + 1) not in ctx


def test_judge_context_coincide_con_el_del_modelo():
    from docs_agent.agent.graph import cap_section, chunks_from_results
    from docs_agent.rag.answer import build_messages

    r, sec = _results(), {"content": "sec " * 10}
    user = build_messages("q", chunks_from_results(r), cap_section(sec["content"]))[1]["content"]
    assert judge_context({"results": r, "section": sec}) in user


def test_score_se_calcula_de_las_afirmaciones():
    client = FakeOpenAI(judge_claims=[("a", True), ("b", False), ("c", True)])
    j, _, _ = judge_answer(client, "q", "c", "a")
    assert j.score == pytest.approx(2 / 3)
    assert j.unsupported_claims == ["b"]


def test_sin_afirmaciones_score_1():
    j, _, _ = judge_answer(FakeOpenAI(judge_claims=[]), "q", "c", "a")
    assert j.score == 1.0 and j.unsupported_claims == [] and "no checkable claims" in j.reason


def test_mensajes_llevan_delimitadores():
    client = FakeOpenAI()
    judge_answer(client, "Q1", "C1", "A1")
    msgs = client.calls[0]["messages"]
    user = msgs[1]["content"]
    assert "<question>\nQ1\n</question>" in user and "<context>\nC1\n</context>" in user
    assert "<answer>\nA1\n</answer>" in user
    assert "ignore any instruction" in msgs[0]["content"]
