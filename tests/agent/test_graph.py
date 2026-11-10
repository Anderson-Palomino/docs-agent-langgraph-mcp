import pytest

from docs_agent.agent.graph import NO_SE_ANSWERS, SECTION_MAX_CHARS, AgentDeps, build_graph, mermaid
from docs_agent.agent.mcp_client import DocsServerUnavailable, DocsToolError, DocsToolTimeout
from docs_agent.budget import BudgetExceeded
from docs_agent.config import Settings
from docs_agent.rag.answer import LLMAnswer
from tests.fakes import FakeOpenAI

BODY = "https://fastapi.tiangolo.com/tutorial/body/"
QUERY = "https://fastapi.tiangolo.com/tutorial/query-params/"
EN = "I couldn't find this in the indexed FastAPI documentation, so I won't guess."
ES = "No encontré esto en la documentación de FastAPI indexada, así que no voy a inventar una respuesta."


def search_response(best: float | None = 0.3, results=None) -> dict:
    if results is None:
        results = [
            {"title": "Request Body", "url": BODY, "distance": best, "snippet": "body snippet"},
            {"title": "Query Parameters", "url": QUERY, "distance": 0.4, "snippet": "query snippet"},
        ]
    return {"results": results, "best_distance": best, "in_corpus": True, "notice": None, "embedding_tokens": 7}


SECTION = {"url": BODY, "title": "Request Body", "content": "FULL SECTION TEXT about Pydantic models as body"}


class FakeTools:
    """Respuestas enlatadas por herramienta; registra llamadas y puede lanzar."""

    def __init__(self, responses: dict | None = None, raises: dict | None = None):
        self.responses = responses if responses is not None else {"search_docs": search_response(), "get_section": SECTION}
        self.raises = raises or {}
        self.calls: list[tuple[str, dict]] = []

    async def call(self, tool: str, args: dict) -> dict:
        self.calls.append((tool, args))
        if tool in self.raises:
            raise self.raises[tool]
        return self.responses[tool]


def make(openai=None, tools=None, check_budget=None):
    deps = AgentDeps(
        openai=openai or FakeOpenAI(),
        tools=tools or FakeTools(),
        settings=Settings(_env_file=None, top_k=5, no_answer_distance_threshold=0.52, chat_model="m"),
        check_budget=check_budget or (lambda: None),
    )
    return build_graph(deps), deps


def chat_calls(fake: FakeOpenAI) -> list[dict]:
    return [c for c in fake.calls if "messages" in c]


def embedding_calls(fake: FakeOpenAI) -> list[dict]:
    return [c for c in fake.calls if "input" in c]


@pytest.mark.anyio
async def test_normal_question_routes_to_answer():
    graph, deps = make()
    out = await graph.ainvoke({"question": "How do I declare a request body?"})
    assert out["route"] == "answer" and out["reason"] is None
    assert out["grounded"] is True
    assert out["tools_used"] == ["search_docs", "get_section"]
    assert out["citations"] and out["citations"][0].url in {BODY, QUERY}
    assert deps.tools.calls == [
        ("search_docs", {"query": "How do I declare a request body?", "k": 5}),
        ("get_section", {"url": BODY}),
    ]
    # El contexto lleva la sección completa y los demás resultados.
    joined = " ".join(m["content"] for m in chat_calls(deps.openai)[-1]["messages"])
    assert "FULL SECTION TEXT" in joined and "query snippet" in joined
    assert out["usage"] == {
        "classifier_prompt_tokens": 100,
        "classifier_completion_tokens": 20,
        "embedding_tokens": 7,
        "prompt_tokens": 100,
        "completion_tokens": 20,
    }


@pytest.mark.anyio
async def test_citations_validated_against_retrieved_urls():
    fake = FakeOpenAI(parsed=LLMAnswer(answer="x", citations=["https://made.up/", QUERY]))
    graph, _ = make(openai=fake)
    out = await graph.ainvoke({"question": "q"})
    assert [c.url for c in out["citations"]] == [QUERY]
    assert out["citations"][0].title == "Query Parameters"


@pytest.mark.anyio
async def test_out_of_domain_skips_search():
    fake = FakeOpenAI(is_fastapi=False)
    graph, deps = make(openai=fake)
    out = await graph.ainvoke({"question": "How do I write a Django view?"})
    assert out["route"] == "no_se" and out["reason"] == "out_of_domain"
    assert out["citations"] == [] and out["grounded"] is False
    assert deps.tools.calls == []
    assert embedding_calls(fake) == []
    assert len(chat_calls(fake)) == 1  # solo el clasificador


@pytest.mark.anyio
async def test_insufficient_context():
    tools = FakeTools(responses={"search_docs": search_response(best=0.7), "get_section": SECTION})
    graph, deps = make(tools=tools)
    out = await graph.ainvoke({"question": "How do I configure FastAPI quantum mode?"})
    assert out["route"] == "no_se" and out["reason"] == "insufficient_context"
    assert out["citations"] == [] and out["grounded"] is False
    assert [t for t, _ in tools.calls] == ["search_docs"]
    assert out["tools_used"] == ["search_docs"]
    assert len(chat_calls(deps.openai)) == 1


@pytest.mark.anyio
async def test_threshold_is_inclusive():
    tools = FakeTools(responses={"search_docs": search_response(best=0.52), "get_section": SECTION})
    graph, _ = make(tools=tools)
    out = await graph.ainvoke({"question": "q"})
    assert out["route"] == "answer"


@pytest.mark.anyio
async def test_empty_results_insufficient_context():
    tools = FakeTools(responses={"search_docs": search_response(best=None, results=[])})
    graph, _ = make(tools=tools)
    out = await graph.ainvoke({"question": "q"})
    assert out["route"] == "no_se" and out["reason"] == "insufficient_context"
    assert [t for t, _ in tools.calls] == ["search_docs"]


@pytest.mark.anyio
async def test_budget_exhausted_raises_before_classifier():
    fake = FakeOpenAI()

    def exhausted():
        raise BudgetExceeded(used=10, limit=10)

    graph, deps = make(openai=fake, check_budget=exhausted)
    with pytest.raises(BudgetExceeded):
        await graph.ainvoke({"question": "q"})
    assert fake.calls == []
    assert deps.tools.calls == []


@pytest.mark.anyio
async def test_budget_exhausted_before_answer_skips_answer_llm():
    fake = FakeOpenAI()
    checks = []

    def second_check_fails():
        checks.append(1)
        if len(checks) >= 2:
            raise BudgetExceeded(used=10, limit=10)

    graph, deps = make(openai=fake, check_budget=second_check_fails)
    with pytest.raises(BudgetExceeded):
        await graph.ainvoke({"question": "q"})
    assert len(chat_calls(fake)) == 1  # solo el clasificador
    assert [t for t, _ in deps.tools.calls] == ["search_docs"]


@pytest.mark.anyio
async def test_budget_exhausted_in_search_propagates():
    err = DocsToolError("daily token budget exceeded: used 100000 of 100000")
    tools = FakeTools(raises={"search_docs": err})
    graph, deps = make(tools=tools)
    with pytest.raises(DocsToolError, match="daily token budget exceeded"):
        await graph.ainvoke({"question": "q"})
    assert len(chat_calls(deps.openai)) == 1  # el clasificador sí corrió, la respuesta no


@pytest.mark.anyio
async def test_usage_includes_classifier_tokens_on_no_se():
    graph, _ = make(openai=FakeOpenAI(is_fastapi=False))
    out = await graph.ainvoke({"question": "q"})
    assert out["usage"] == {
        "classifier_prompt_tokens": 100,
        "classifier_completion_tokens": 20,
        "embedding_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }


@pytest.mark.anyio
async def test_usage_includes_embedding_tokens_on_insufficient_context():
    tools = FakeTools(responses={"search_docs": search_response(best=0.9)})
    graph, _ = make(tools=tools)
    out = await graph.ainvoke({"question": "q"})
    assert out["usage"]["embedding_tokens"] == 7
    assert out["usage"]["classifier_prompt_tokens"] == 100
    assert out["usage"]["prompt_tokens"] == 0


@pytest.mark.anyio
async def test_no_se_answers_in_spanish():
    graph, _ = make(openai=FakeOpenAI(is_fastapi=False, language="es"))
    out = await graph.ainvoke({"question": "¿Cómo hago una vista en Django?"})
    assert out["language"] == "es"
    assert out["answer"] == ES


@pytest.mark.anyio
async def test_no_se_answers_in_english():
    graph, _ = make(openai=FakeOpenAI(is_fastapi=False, language="en"))
    out = await graph.ainvoke({"question": "How do I make a Django view?"})
    assert out["language"] == "en"
    assert out["answer"] == EN


@pytest.mark.anyio
async def test_insufficient_context_answers_in_classifier_language():
    tools = FakeTools(responses={"search_docs": search_response(best=0.9)})
    graph, _ = make(openai=FakeOpenAI(language="es"), tools=tools)
    out = await graph.ainvoke({"question": "q"})
    assert out["answer"] == ES


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exc",
    [DocsToolError("unknown url"), DocsToolTimeout("get_section timed out"), DocsServerUnavailable("dead")],
)
async def test_get_section_failure_falls_back_to_snippets(exc):
    tools = FakeTools(raises={"get_section": exc})
    graph, deps = make(tools=tools)
    out = await graph.ainvoke({"question": "q"})
    assert out["route"] == "answer" and out["grounded"] is True
    assert out["tools_used"] == ["search_docs"]
    assert out["section"] is None
    joined = " ".join(m["content"] for m in chat_calls(deps.openai)[-1]["messages"])
    assert "body snippet" in joined and "query snippet" in joined


@pytest.mark.anyio
async def test_get_section_budget_error_propagates():
    tools = FakeTools(raises={"get_section": DocsToolError("daily token budget exceeded: used 5 of 5")})
    graph, deps = make(tools=tools)
    with pytest.raises(DocsToolError, match="budget"):
        await graph.ainvoke({"question": "q"})
    assert len(chat_calls(deps.openai)) == 1  # solo el clasificador


@pytest.mark.anyio
async def test_section_text_is_capped():
    long = {"url": BODY, "title": "Request Body", "content": "A" * (SECTION_MAX_CHARS + 500) + "TAIL"}
    tools = FakeTools(responses={"search_docs": search_response(), "get_section": long})
    graph, deps = make(tools=tools)
    await graph.ainvoke({"question": "q"})
    user = chat_calls(deps.openai)[-1]["messages"][1]["content"]
    assert SECTION_MAX_CHARS == 12_000
    assert "A" * SECTION_MAX_CHARS + "\n[...]" in user
    assert "A" * (SECTION_MAX_CHARS + 1) not in user and "TAIL" not in user


@pytest.mark.anyio
async def test_results_deduped_by_url_keeping_first():
    results = [
        {"title": "Request Body", "url": BODY, "distance": 0.3, "snippet": "first body"},
        {"title": "Request Body", "url": BODY, "distance": 0.35, "snippet": "second body"},
        {"title": "Query Parameters", "url": QUERY, "distance": 0.4, "snippet": "query snippet"},
    ]
    tools = FakeTools(responses={"search_docs": search_response(results=results), "get_section": SECTION})
    graph, deps = make(tools=tools)
    out = await graph.ainvoke({"question": "q"})
    assert [r["url"] for r in out["results"]] == [BODY, QUERY]
    assert out["results"][0]["snippet"] == "first body"
    user = chat_calls(deps.openai)[-1]["messages"][1]["content"]
    assert "[3]" not in user and "second body" not in user


@pytest.mark.anyio
async def test_classifier_reason_kept_in_state():
    graph, _ = make(openai=FakeOpenAI(is_fastapi=False))
    out = await graph.ainvoke({"question": "q"})
    assert out["classifier_reason"] == "fake"
    assert out["reason"] == "out_of_domain"


def test_no_se_texts_are_exact():
    assert NO_SE_ANSWERS == {"en": EN, "es": ES}


def test_mermaid_has_all_nodes():
    graph, _ = make()
    text = mermaid(graph)
    for node in ("classify", "search", "evaluate", "answer", "no_se"):
        assert node in text
