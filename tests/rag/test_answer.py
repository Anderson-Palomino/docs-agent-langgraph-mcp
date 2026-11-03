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
