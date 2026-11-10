import pytest

from docs_agent.budget import KIND_ASK, record_usage, tokens_used_today

pytestmark = pytest.mark.integration


def test_ask_happy_path(client, seeded_corpus):
    r = client.post("/ask", json={"question": "How do I declare a body?"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True and body["citations"][0]["url"].startswith("https://fastapi.tiangolo.com/")
    # Contrato extendido (D33): se añade `classifier_tokens`; las tres claves de la semana 1 siguen.
    assert set(body["usage"]) == {"embedding_tokens", "prompt_tokens", "completion_tokens", "classifier_tokens"}
    assert "retrieved" not in body


@pytest.mark.parametrize("q", ["", "   ", "x" * 1001])
def test_ask_rejects_bad_question(client, q):
    assert client.post("/ask", json={"question": q}).status_code == 422


def test_ask_empty_corpus_503(client):
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and "ingest" in r.json()["detail"]


def test_ask_budget_exhausted_429(client, seeded_corpus, db_conn, settings_factory):
    record_usage(db_conn, KIND_ASK, 10**9)
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 429 and r.json()["detail"] == "Daily token budget exhausted"


def test_ask_upstream_error_502_and_no_usage(client_with_failing_openai, seeded_corpus, db_conn):
    r = client_with_failing_openai.post("/ask", json={"question": "hi"})
    assert r.status_code == 502 and r.json()["detail"] == "Upstream model error"
    assert tokens_used_today(db_conn, KIND_ASK) == 0


def test_ask_records_usage(client, seeded_corpus, db_conn):
    client.post("/ask", json={"question": "hi"})
    assert tokens_used_today(db_conn, KIND_ASK) > 0


def test_debug_includes_retrieved(client, seeded_corpus):
    assert client.post("/ask?debug=true", json={"question": "hi"}).json()["retrieved"]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_ask_and_health_only_see_configured_docs_version(make_client, db_conn):
    from docs_agent.ingest.chunk import Chunk
    from docs_agent.ingest.store import replace_corpus
    from tests.fakes import FakeOpenAI

    old = Chunk("https://fastapi.tiangolo.com/old/", "Old", "old docs version", 3)
    new = Chunk("https://fastapi.tiangolo.com/new/", "New", "new docs version", 3)
    replace_corpus(db_conn, "old-ref", [old], [FakeOpenAI.vector_for(old.content)])
    replace_corpus(db_conn, "test-ref", [new], [FakeOpenAI.vector_for(new.content)])
    c = make_client(FakeOpenAI())
    body = c.post("/ask?debug=true", json={"question": "docs"}).json()
    assert [r["url"] for r in body["retrieved"]] == [new.url]
    assert c.get("/health").json()["chunks"] == 1


def test_ask_chat_only_non_api_error_502_and_no_usage(make_client, seeded_corpus, db_conn):
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(fail_chat=True))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 502 and r.json()["detail"] == "Upstream model error"
    assert tokens_used_today(db_conn, KIND_ASK) == 0


def test_ask_without_api_key_503(make_client, seeded_corpus):
    from tests.fakes import FakeOpenAI

    fake = FakeOpenAI()
    r = make_client(fake, openai_api_key="").post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json()["detail"] == "OPENAI_API_KEY not configured"
    assert fake.calls == []


def test_openai_client_has_timeout_and_retries(monkeypatch):
    from docs_agent import api
    from docs_agent.config import Settings

    monkeypatch.setattr(api, "get_settings", lambda: Settings(_env_file=None, openai_api_key="sk-test"))
    client = api.get_openai()
    assert client.timeout == 30 and client.max_retries == 2


# --- /ask sobre el grafo (Task 9, D33) ---

BODY_CHUNK = "Declare a request body with a Pydantic model."  # texto exacto de un fragmento: distancia 0
BODY_SECTION_URL = "https://fastapi.tiangolo.com/tutorial/body/#request-body"


def test_ask_returns_route_and_reason(make_client, seeded_corpus):
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(), no_answer_distance_threshold=0.52)
    body = c.post("/ask", json={"question": BODY_CHUNK}).json()
    assert body["route"] == "answer"
    assert "reason" in body and body["reason"] is None
    assert body["grounded"] is True and body["citations"][0]["url"] == BODY_SECTION_URL

    # Con el umbral real, una pregunta sin fragmento cercano (vectores ~1.0) no llega al LLM de respuesta.
    body = c.post("/ask", json={"question": "How do I declare a body?"}).json()
    assert body["route"] == "no_se" and body["reason"] == "insufficient_context"
    assert body["grounded"] is False and body["citations"] == []


def test_ask_out_of_domain_no_se(make_client, seeded_corpus):
    from tests.fakes import FakeOpenAI

    fake = FakeOpenAI(is_fastapi=False)
    c = make_client(fake)
    r = c.post("/ask", json={"question": "How do I write a Django REST serializer?"})
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "no_se" and body["reason"] == "out_of_domain"
    assert body["grounded"] is False and body["citations"] == []
    assert body["usage"]["embedding_tokens"] == 0  # fuera de dominio no busca
    assert all("input" not in call for call in fake.calls)


class _RaisingTools:
    def __init__(self, exc: Exception):
        self.exc = exc
        self.calls: list[tuple[str, dict]] = []

    async def call(self, tool: str, args: dict) -> dict:
        self.calls.append((tool, args))
        raise self.exc


def test_ask_docs_server_unavailable_503(make_client, seeded_corpus, db_conn):
    from docs_agent.agent.mcp_client import DocsServerUnavailable
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(), tools=_RaisingTools(DocsServerUnavailable("MCP server unavailable calling search_docs")))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json()["detail"] == "Docs server unavailable"
    assert tokens_used_today(db_conn, KIND_ASK) == 0


def test_ask_docs_tool_timeout_503(make_client, seeded_corpus):
    from docs_agent.agent.mcp_client import DocsToolTimeout
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(), tools=_RaisingTools(DocsToolTimeout("MCP tool search_docs exceeded 15.0s")))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json()["detail"] == "Docs server unavailable"


def test_ask_budget_exhausted_in_tool_429_no_usage(make_client, seeded_corpus, db_conn):
    from docs_agent.agent.mcp_client import DocsToolError
    from tests.fakes import FakeOpenAI

    # Así llega por MCP el `BudgetExceeded` del servidor (scope `ask`): `DocsToolError` con su mensaje.
    exc = DocsToolError("Error executing tool search_docs: daily token budget exceeded: used 200000 of 200000")
    tools = _RaisingTools(exc)
    c = make_client(FakeOpenAI(), tools=tools)
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 429 and r.json()["detail"] == "Daily token budget exhausted"
    assert tools.calls and tools.calls[0][0] == "search_docs"
    assert tokens_used_today(db_conn, KIND_ASK) == 0


def test_ask_other_tool_error_502(make_client, seeded_corpus, db_conn):
    from docs_agent.agent.mcp_client import DocsToolError
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(), tools=_RaisingTools(DocsToolError("Error executing tool search_docs: Database unavailable")))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 502 and r.json()["detail"] == "Docs tool error"
    assert tokens_used_today(db_conn, KIND_ASK) == 0


def test_ask_usage_has_classifier_tokens(client, seeded_corpus, db_conn):
    body = client.post("/ask", json={"question": "How do I declare a body?"}).json()
    usage = body["usage"]
    # FakeOpenAI: 100 prompt + 20 completion por llamada de chat (clasificador y respuesta).
    assert usage["classifier_tokens"] == 120
    assert usage["prompt_tokens"] == 100 and usage["completion_tokens"] == 20
    assert usage["embedding_tokens"] > 0
    # `ask` = lo que registró la API (clasificador + respuesta) + los embeddings que registró la herramienta.
    assert tokens_used_today(db_conn, KIND_ASK) == 120 + 120 + usage["embedding_tokens"]


def test_ask_debug_retrieved_comes_from_search_docs(client, seeded_corpus):
    body = client.post("/ask?debug=true", json={"question": "hi"}).json()
    assert body["retrieved"] and set(body["retrieved"][0]) == {"url", "title", "distance"}


def test_ask_response_keeps_n8n_fields(client, seeded_corpus):
    """Claves de `/ask` que leen `integrations/n8n/workflows/*.json` (01-ask-log: answer, grounded, citations
    [{url,title}], usage.{embedding,prompt,completion}_tokens; error: detail). Deben seguir existiendo."""
    body = client.post("/ask", json={"question": "How do I declare a body?"}).json()
    assert {"answer", "grounded", "citations", "usage"} <= set(body)
    assert {"embedding_tokens", "prompt_tokens", "completion_tokens"} <= set(body["usage"])
    assert set(body["citations"][0]) == {"url", "title"}
    assert "detail" in client.post("/ask", json={"question": ""}).json()


def test_lifespan_builds_stdio_params_with_ask_scope(monkeypatch):
    """La API lanza el servidor MCP con `MCP_BUDGET_SCOPE=ask` (D29) y lo cierra al apagar, sin abrirlo antes
    de la primera llamada (sesión perezosa, D30)."""
    from fastapi.testclient import TestClient

    from docs_agent import api
    from docs_agent.agent import mcp_client
    from docs_agent.config import Settings

    settings = Settings(_env_file=None, openai_api_key="sk-test", mcp_call_timeout_s=7.5)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    built: list = []
    real_params = mcp_client.stdio_params

    def spy_params(s, scope):
        params = real_params(s, scope)
        built.append((scope, params))
        return params

    monkeypatch.setattr(mcp_client, "stdio_params", spy_params)
    closed: list[bool] = []
    real_aclose = mcp_client.DocsMCPClient.aclose

    async def spy_aclose(self):
        closed.append(True)
        await real_aclose(self)

    monkeypatch.setattr(mcp_client.DocsMCPClient, "aclose", spy_aclose)
    with TestClient(api.app):
        docs_tools = api.app.state.docs_tools
        assert isinstance(docs_tools, mcp_client.DocsMCPClient)
        assert docs_tools.call_timeout_s == 7.5
        assert docs_tools._session is None  # perezoso: no lanzó el subproceso
        assert [scope for scope, _ in built] == ["ask"]
        assert built[0][1].env["MCP_BUDGET_SCOPE"] == "ask"
        assert closed == []
    assert closed == [True]
