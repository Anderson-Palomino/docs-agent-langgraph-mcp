import pytest
from fastapi import HTTPException

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
    client = api.make_openai()
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
    # El clasificador ya gastó (100 + 20): se registra aunque la petición falle; un MCP caído no gasta gratis.
    assert tokens_used_today(db_conn, KIND_ASK) == 120


def test_ask_record_failure_keeps_mapped_error(make_client, seeded_corpus, monkeypatch, caplog):
    """Postgres cae al registrar el gasto tras un error del grafo: sigue el 503, no un 500 (una línea de aviso)."""
    import psycopg

    from docs_agent.agent.mcp_client import DocsServerUnavailable
    from tests.fakes import FakeOpenAI

    def record_fails(conn, deps):
        raise psycopg.OperationalError("connection to server at 127.0.0.1 failed: secret-ish detail")

    monkeypatch.setattr("docs_agent.api.record_spent", record_fails)
    c = make_client(FakeOpenAI(), tools=_RaisingTools(DocsServerUnavailable("down")))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json()["detail"] == "Docs server unavailable"
    warnings = [rec for rec in caplog.records if rec.name == "docs_agent.api" and rec.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "OperationalError" in warnings[0].getMessage() and "127.0.0.1" not in warnings[0].getMessage()


def test_ask_record_failure_on_success_propagates(make_client, seeded_corpus, monkeypatch):
    import psycopg

    from tests.fakes import FakeOpenAI

    def record_fails(conn, deps):
        raise psycopg.OperationalError("db down")

    monkeypatch.setattr("docs_agent.api.record_spent", record_fails)
    c = make_client(FakeOpenAI())
    with pytest.raises(psycopg.OperationalError):
        c.post("/ask", json={"question": "hi"})


def test_ask_docs_tool_timeout_503(make_client, seeded_corpus):
    from docs_agent.agent.mcp_client import DocsToolTimeout
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(), tools=_RaisingTools(DocsToolTimeout("MCP tool search_docs exceeded 15.0s")))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json()["detail"] == "Docs server unavailable"


def test_ask_budget_exhausted_in_tool_429_records_classifier_usage(make_client, seeded_corpus, db_conn):
    from docs_agent.agent.mcp_client import DocsToolError
    from tests.fakes import FakeOpenAI

    # Así llega por MCP el `BudgetExceeded` del servidor (scope `ask`): `DocsToolError` con su mensaje.
    exc = DocsToolError("Error executing tool search_docs: daily token budget exceeded: used 200000 of 200000")
    tools = _RaisingTools(exc)
    c = make_client(FakeOpenAI(), tools=tools)
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 429 and r.json()["detail"] == "Daily token budget exhausted"
    assert tools.calls and tools.calls[0][0] == "search_docs"
    assert tokens_used_today(db_conn, KIND_ASK) == 120  # solo el clasificador, que sí se gastó


def test_ask_other_tool_error_502(make_client, seeded_corpus, db_conn):
    from docs_agent.agent.mcp_client import DocsToolError
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(), tools=_RaisingTools(DocsToolError("Error executing tool search_docs: Database unavailable")))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 502 and r.json()["detail"] == "Docs tool error"
    assert tokens_used_today(db_conn, KIND_ASK) == 120


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


def test_ask_answer_failure_records_only_classifier(make_client, seeded_corpus, db_conn):
    """Falla la llamada de respuesta: se registra el clasificador y los embeddings (servidor), no la respuesta."""
    from tests.fakes import FakeOpenAI

    class FailOnSecondChat(FakeOpenAI):
        def _parse_chat(self, model, messages, response_format, temperature=None):
            if any("messages" in c for c in self.calls):
                raise __import__("openai").OpenAIError("boom on answer")
            return super()._parse_chat(model, messages, response_format, temperature)

    fake = FailOnSecondChat()
    r = make_client(fake).post("/ask", json={"question": "How do I declare a body?"})
    assert r.status_code == 502 and r.json()["detail"] == "Upstream model error"
    embedding_tokens = sum(len(c["input"][0].split()) for c in fake.calls if "input" in c)
    assert embedding_tokens > 0
    assert tokens_used_today(db_conn, KIND_ASK) == 120 + embedding_tokens


# --- Rate limit por IP (Task 7) ---


class CountingTools:
    """Doble de herramientas que cuenta llamadas: un 429 por rate limit no debe tocar el grafo."""

    def __init__(self):
        self.calls = 0

    async def call(self, tool, args):
        from docs_agent.agent.mcp_client import DocsServerUnavailable

        self.calls += 1
        raise DocsServerUnavailable("down")


def _peer_client(peer_ip):
    from fastapi.testclient import TestClient

    from docs_agent.api import app

    return TestClient(app, client=(peer_ip, 50000))


def test_ask_rate_limit_429_with_retry_after(make_client, seeded_corpus):
    from tests.fakes import FakeOpenAI

    tools = CountingTools()
    make_client(FakeOpenAI(), tools=tools, ask_rate_limit_per_hour=2)
    c = _peer_client("203.0.113.7")
    # Las dos primeras pasan el límite y llegan al grafo (el doble responde 503); la tercera se corta antes.
    for _ in range(2):
        assert c.post("/ask", json={"question": "x"}).status_code == 503
    calls_before = tools.calls
    assert calls_before >= 1
    r = c.post("/ask", json={"question": "x"})
    assert r.status_code == 429
    assert r.json()["detail"] == "Rate limit exceeded"
    assert int(r.headers["Retry-After"]) >= 1
    assert tools.calls == calls_before


def test_ask_rate_limit_is_first_check(make_client):
    """Sin clave de OpenAI y con el límite agotado, gana el 429 del rate limit, no el 503."""
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1)
    c = _peer_client("203.0.113.8")
    assert c.post("/ask", json={"question": "x"}).status_code == 503
    r = c.post("/ask", json={"question": "x"})
    assert r.status_code == 429 and r.json()["detail"] == "Rate limit exceeded"


def test_ask_rate_limit_other_ip_via_trusted_proxy_passes(make_client):
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="10.0.0.0/8", trusted_proxy_hops=0)
    c = _peer_client("10.0.0.1")
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 503
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 503


def test_ask_rate_limit_xff_ignored_without_trusted_proxy(make_client):
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1)
    c = _peer_client("203.0.113.9")
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 503
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429


def test_ask_rate_limit_429_logs_masked_key(make_client, caplog):
    import logging

    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="*", trusted_proxy_hops=0)
    c = _peer_client("10.0.0.1")
    h = {"X-Forwarded-For": "9.9.9.9, 181.65.10.20"}
    with caplog.at_level(logging.WARNING, logger="docs_agent.api"):
        r1 = c.post("/ask", json={"question": "x"}, headers=h)
        assert not [x for x in caplog.records if "rate limit 429" in x.getMessage()]
        r2 = c.post("/ask", json={"question": "x"}, headers=h)
    assert r1.status_code == 503 and r2.status_code == 429
    assert r2.json() == {"detail": "Rate limit exceeded"} and "retry-after" in r2.headers
    recs = [x for x in caplog.records if x.name == "docs_agent.api" and "rate limit 429" in x.getMessage()]
    assert len(recs) == 1 and recs[0].levelno == logging.WARNING
    msg = recs[0].getMessage()
    for part in ("key=181.65.x.x", "source=xff", "index_from_right=0", "entries=2", "9.9.x.x", "181.65.x.x"):
        assert part in msg
    assert "181.65.10.20" not in msg and "9.9.9.9" not in msg


def test_ask_rate_limit_429_log_caps_xff_entries(make_client, caplog):
    import logging

    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="*", trusted_proxy_hops=0)
    c = _peer_client("10.0.0.1")
    h = {"X-Forwarded-For": ", ".join(f"9.{i}.9.9" for i in range(1, 9)) + ", 181.65.10.20"}  # 9 entradas
    with caplog.at_level(logging.WARNING, logger="docs_agent.api"):
        c.post("/ask", json={"question": "x"}, headers=h)
        r2 = c.post("/ask", json={"question": "x"}, headers=h)
    assert r2.status_code == 429
    recs = [x for x in caplog.records if x.name == "docs_agent.api" and "rate limit 429" in x.getMessage()]
    msg = recs[0].getMessage()
    assert "entries=9" in msg
    xff = msg.split("xff=[", 1)[1].rstrip("]")
    assert xff.startswith("…, ")
    assert len(xff[len("…, "):].split(", ")) == 5
    assert xff.endswith("181.65.x.x") and "9.1.x.x" not in msg


def test_ask_rate_limit_429_log_has_key_id_not_ip(make_client, caplog):
    import logging

    from docs_agent.ratelimit import key_id
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="*", trusted_proxy_hops=0)
    c = _peer_client("10.0.0.1")
    h = {"X-Forwarded-For": "181.65.10.20"}
    with caplog.at_level(logging.WARNING, logger="docs_agent.api"):
        c.post("/ask", json={"question": "x"}, headers=h)
        c.post("/ask", json={"question": "x"}, headers=h)
    msg = [x for x in caplog.records if "rate limit 429" in x.getMessage()][0].getMessage()
    assert f"key_id={key_id('181.65.10.20')}" in msg


def test_health_never_rate_limited(make_client):
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(), ask_rate_limit_per_hour=1)
    for _ in range(5):
        assert c.get("/health").status_code == 200


def test_startup_warns_when_rate_limit_without_trusted_proxies(monkeypatch, caplog):
    import logging

    from fastapi.testclient import TestClient

    from docs_agent import api
    from docs_agent.config import Settings

    msg = "rate limit keyed by socket IP; set TRUSTED_PROXY_IPS behind a proxy"
    monkeypatch.setattr(api, "get_settings", lambda: Settings(_env_file=None, ask_rate_limit_per_hour=5))
    with caplog.at_level(logging.WARNING, logger="docs_agent.api"), TestClient(api.app):
        pass
    assert msg in caplog.text

    caplog.clear()
    del api.app.state.rate_limit
    monkeypatch.setattr(
        api, "get_settings", lambda: Settings(_env_file=None, ask_rate_limit_per_hour=5, trusted_proxy_ips="*")
    )
    with caplog.at_level(logging.WARNING, logger="docs_agent.api"), TestClient(api.app):
        pass
    assert msg not in caplog.text


def test_startup_fails_on_invalid_trusted_proxy_ips(monkeypatch):
    from fastapi.testclient import TestClient

    from docs_agent import api
    from docs_agent.config import Settings

    monkeypatch.setattr(api, "get_settings", lambda: Settings(_env_file=None, trusted_proxy_ips="not-an-ip"))
    with pytest.raises(ValueError):
        with TestClient(api.app):
            pass


def test_ask_rate_limit_precedes_db_dependency(make_client):
    """Con el límite agotado, 429 aunque la base esté caída, y sin abrir ninguna conexión."""
    from docs_agent.api import app, get_conn
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1)
    c = _peer_client("203.0.113.20")
    assert c.post("/ask", json={"question": "x"}).status_code == 503  # consume el cupo (sin clave de OpenAI)
    opened = []

    def broken_conn():
        opened.append(1)
        raise HTTPException(status_code=503, detail="Database unavailable")

    app.dependency_overrides[get_conn] = broken_conn
    r = c.post("/ask", json={"question": "x"})
    assert r.status_code == 429 and r.json()["detail"] == "Rate limit exceeded"
    assert opened == []


def test_ask_rate_limit_uses_all_xff_header_lines(make_client):
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="10.0.0.0/8", trusted_proxy_hops=0)
    c = _peer_client("10.0.0.1")
    # Dos líneas de cabecera: la primera la controla el cliente; cuenta la última (la del proxy).
    h1 = [("X-Forwarded-For", "6.6.6.6"), ("X-Forwarded-For", "1.1.1.1")]
    h2 = [("X-Forwarded-For", "7.7.7.7"), ("X-Forwarded-For", "1.1.1.1")]
    assert c.post("/ask", json={"question": "x"}, headers=h1).status_code == 503
    assert c.post("/ask", json={"question": "x"}, headers=h2).status_code == 429


def test_ask_rate_limit_ipv6_same_slash_64_shares_quota(make_client):
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="10.0.0.0/8", trusted_proxy_hops=0)
    c = _peer_client("10.0.0.1")
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "2001:db8:1:2::1"}).status_code == 503
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "2001:db8:1:2::99"}).status_code == 429
    assert c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "2001:db8:1:3::1"}).status_code == 503


def test_root_redirects_to_docs(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/docs"


CHAIN_A = "38.19.1.2, 172.68.3.4, 10.29.5.6"
CHAIN_C = "179.7.8.9, 172.68.3.4, 10.29.5.6"


def test_ask_rate_limit_hops_independent_quotas_and_spoof_ignored(make_client):
    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="*", trusted_proxy_hops=2)
    c = _peer_client("10.29.5.6")
    post = lambda xff: c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": xff}).status_code  # noqa: E731
    assert post(CHAIN_A) == 503
    assert post(CHAIN_C) == 503  # otro cliente, mismo borde y mismo salto: cupo propio
    assert post("203.0.113.7, " + CHAIN_A) == 429  # cabecera falsificada a la izquierda: misma clave que A
    assert post(CHAIN_A) == 429


def _cf_log(make_client, caplog, cf_header):
    import logging

    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="*", trusted_proxy_hops=2)
    c = _peer_client("10.29.5.6")
    h = {"X-Forwarded-For": CHAIN_A, **cf_header}
    with caplog.at_level(logging.WARNING, logger="docs_agent.api"):
        c.post("/ask", json={"question": "x"}, headers=h)
        r = c.post("/ask", json={"question": "x"}, headers=h)
    assert r.status_code == 429
    return [x for x in caplog.records if "rate limit 429" in x.getMessage()][0].getMessage()


@pytest.mark.parametrize(
    "cf_header, expected",
    [({"CF-Connecting-IP": "38.19.1.2"}, "yes"), ({"CF-Connecting-IP": "8.8.4.4"}, "no"), ({}, "absent")],
)
def test_ask_rate_limit_429_logs_cf_ip_match(make_client, caplog, cf_header, expected):
    msg = _cf_log(make_client, caplog, cf_header)
    assert f"cf_ip_match={expected}" in msg
    assert "source=xff index_from_right=2 entries=3" in msg
    assert "38.19.1.2" not in msg and "8.8.4.4" not in msg


def test_negative_trusted_proxy_hops_rejected():
    from docs_agent.config import Settings

    with pytest.raises(ValueError):
        Settings(_env_file=None, trusted_proxy_hops=-1)


def test_ask_rate_limit_short_chains_share_one_quota_and_log(make_client, caplog):
    import logging

    from tests.fakes import FakeOpenAI

    make_client(FakeOpenAI(), openai_api_key="", ask_rate_limit_per_hour=1, trusted_proxy_ips="*", trusted_proxy_hops=2)
    c = _peer_client("10.29.5.6")
    with caplog.at_level(logging.WARNING):
        r1 = c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "38.19.1.2, 10.29.5.6"})
        r2 = c.post("/ask", json={"question": "x"}, headers={"X-Forwarded-For": "179.7.8.9, 10.29.5.6"})
    assert (r1.status_code, r2.status_code) == (503, 429)
    msg = [x for x in caplog.records if "rate limit 429" in x.getMessage()][0].getMessage()
    assert "key=untrusted-chain" in msg and "source=xff-short" in msg and "cf_ip_match=absent" in msg
    assert "38.19.1.2" not in msg and "179.7.8.9" not in msg
