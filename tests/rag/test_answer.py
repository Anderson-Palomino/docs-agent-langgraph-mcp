from docs_agent.rag.answer import LLMAnswer, answer_question, build_messages, validate_citations
from docs_agent.rag.retrieve import RetrievedChunk
from tests.fakes import FakeOpenAI

CH = [RetrievedChunk(1, "https://fastapi.tiangolo.com/tutorial/body/#x", "Body > X", "...", 0.1),
      RetrievedChunk(2, "https://fastapi.tiangolo.com/tutorial/query/", "Query", "...", 0.2)]


def test_validate_drops_unknown_and_dedupes():
    cits = validate_citations(["https://fastapi.tiangolo.com/tutorial/body/#x", "https://evil.com/",
                               " https://fastapi.tiangolo.com/tutorial/body/#x "], CH)
    assert [c.url for c in cits] == ["https://fastapi.tiangolo.com/tutorial/body/#x"]
    assert cits[0].title == "Body > X"


def test_all_citations_dropped_is_not_grounded():
    fake = FakeOpenAI(parsed=LLMAnswer(answer="x", citations=["https://made.up/"]))
    r = answer_question(fake, "q", CH, model="m")
    assert r.citations == [] and r.grounded is False and r.answer == "x"


def test_messages_contain_numbered_chunks_and_language_rule():
    msgs = build_messages("¿Cómo declaro un body?", CH)
    joined = " ".join(m["content"] for m in msgs)
    assert "[1]" in joined and "https://fastapi.tiangolo.com/tutorial/query/" in joined
    assert "same language" in msgs[0]["content"].lower()


def test_answer_question_uses_temperature_zero_and_given_model():
    fake = FakeOpenAI()
    answer_question(fake, "q", CH, model="my-model")
    assert fake.calls[0]["model"] == "my-model" and fake.calls[0]["temperature"] == 0


def test_section_text_replaces_first_fragment_and_citations_stay_against_chunks():
    msgs = build_messages("q", CH, section_text="FULL SECTION")
    user = msgs[1]["content"]
    assert "[1] Body > X\nURL: https://fastapi.tiangolo.com/tutorial/body/#x\nFULL SECTION" in user
    assert "[2] Query" in user
    fake = FakeOpenAI(parsed=LLMAnswer(answer="x", citations=["https://made.up/", CH[1].url]))
    r = answer_question(fake, "q", CH, model="m", section_text="FULL SECTION")
    assert [c.url for c in r.citations] == [CH[1].url]
