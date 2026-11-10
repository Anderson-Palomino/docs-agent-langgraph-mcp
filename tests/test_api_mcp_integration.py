"""`/ask` respondiendo a través del cliente MCP real (requisito del spec: el grafo pasa por MCP).

Se usa `DocsMCPClient` con `Client(build_server(...))`: el protocolo MCP es el real (JSON-RPC, herramientas,
`structured_content`, errores como `is_error`), en proceso y contra `docs_test`. No se lanza el subproceso stdio
porque el hijo no puede usar `FakeOpenAI` (llamaría a OpenAI de verdad); el transporte stdio real ya está
cubierto en los tests de Task 7 (`list_sources`/`get_section` por stdio, sin tokens).
"""

import pytest
from fastapi.testclient import TestClient
from mcp import Client

from docs_agent import api
from docs_agent.agent.mcp_client import DocsMCPClient
from docs_agent.budget import KIND_ASK, record_usage, tokens_used_today
from docs_agent.config import Settings
from docs_agent.db import connect
from docs_agent.mcp_server.server import build_server
from tests.fakes import FakeOpenAI

pytestmark = pytest.mark.integration

BODY_CHUNK = "Declare a request body with a Pydantic model."
BODY_SECTION_URL = "https://fastapi.tiangolo.com/tutorial/body/#request-body"


@pytest.fixture
def mcp_api(db_conn, monkeypatch):
    fake = FakeOpenAI()
    settings = Settings(_env_file=None, openai_api_key="sk-test", fastapi_docs_ref="test-ref")
    server_settings = settings.model_copy(update={"mcp_budget_scope": "ask"})  # como lo lanza la API (D29)
    docs_tools = DocsMCPClient(
        connect=lambda: Client(build_server(server_settings, conn_factory=connect, client_factory=lambda: fake)),
        call_timeout_s=15,
    )
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    api.app.dependency_overrides[api.get_conn] = lambda: db_conn
    api.app.dependency_overrides[api.get_openai] = lambda: fake
    api.app.dependency_overrides[api.get_docs_tools] = lambda: docs_tools
    # `with`: un solo event loop para todas las peticiones, el mismo en el que vive la sesión MCP.
    with TestClient(api.app) as c:
        yield c, docs_tools, fake
        c.portal.call(docs_tools.aclose)
    api.app.dependency_overrides.clear()


def test_graph_through_mcp_client(mcp_api, seeded_corpus, db_conn):
    c, _, _ = mcp_api
    r = c.post("/ask?debug=true", json={"question": BODY_CHUNK})
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "answer" and body["reason"] is None
    assert body["grounded"] is True and body["citations"][0]["url"] == BODY_SECTION_URL
    assert body["retrieved"][0]["url"] == BODY_SECTION_URL and body["retrieved"][0]["distance"] == 0.0
    # Embeddings los registró el servidor (scope `ask`); clasificador + respuesta, la API.
    assert body["usage"]["embedding_tokens"] > 0
    assert tokens_used_today(db_conn, KIND_ASK) == 120 + 120 + body["usage"]["embedding_tokens"]

    # Segunda pregunta por la misma sesión.
    r = c.post("/ask", json={"question": "How do I declare a body?"})
    assert r.status_code == 200 and r.json()["route"] == "no_se"
    assert r.json()["reason"] == "insufficient_context"


def test_budget_exhausted_in_server_maps_to_429(mcp_api, seeded_corpus, db_conn, monkeypatch):
    """El `BudgetExceeded` del servidor viaja como error MCP y la API lo traduce a 429."""
    c, _, fake = mcp_api
    # El chequeo de la API pasa (no se agotó al empezar) pero el servidor lo ve agotado: se simula que otra
    # petición gastó el presupuesto entre el clasificador y la búsqueda.
    real_build = api.build_graph

    def build_and_exhaust(deps):
        real_classify_budget = deps.check_budget
        state = {"n": 0}

        def check():
            real_classify_budget()
            state["n"] += 1
            if state["n"] == 1:
                record_usage(db_conn, KIND_ASK, 10**9)

        deps.check_budget = check
        return real_build(deps)

    monkeypatch.setattr(api, "build_graph", build_and_exhaust)
    r = c.post("/ask", json={"question": BODY_CHUNK})
    assert r.status_code == 429 and r.json()["detail"] == "Daily token budget exhausted"
    # Lo cortó el servidor (su chequeo va antes del embedding), no el chequeo del nodo `answer`.
    assert [call for call in fake.calls if "input" in call] == []
    assert len([call for call in fake.calls if "messages" in call]) == 1  # solo el clasificador
