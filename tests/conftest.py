import os
from pathlib import Path

import pytest

from docs_agent.config import Settings


def _test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL") or Settings(_env_file=None).test_database_url


def assert_not_demo_db(url: str) -> None:
    """Refuse to run tests against the demo database `docs`."""
    from psycopg.conninfo import conninfo_to_dict

    if conninfo_to_dict(url).get("dbname") == "docs":
        pytest.exit("TEST_DATABASE_URL points at the demo database `docs`; refusing to run tests (they truncate tables).", returncode=2)


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db():
    """Create the `docs_test` database if missing and apply db/init.sql. Never touches `docs`."""
    import psycopg
    import psycopg.sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    url = _test_database_url()
    assert_not_demo_db(url)
    dbname = conninfo_to_dict(url)["dbname"]
    try:
        with psycopg.connect(make_conninfo(url, dbname="postgres"), autocommit=True, connect_timeout=5) as admin:
            exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
            if not exists:
                try:
                    admin.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(dbname)))
                except psycopg.errors.DuplicateDatabase:
                    pass  # created concurrently
        init_sql = (Path(__file__).resolve().parent.parent / "db" / "init.sql").read_text(encoding="utf-8")
        with psycopg.connect(url, autocommit=True, connect_timeout=5) as conn:
            conn.execute(init_sql)
    except psycopg.OperationalError:
        pass  # Postgres down: integration tests skip via db_conn


@pytest.fixture(autouse=True)
def _host_database_url(monkeypatch, _ensure_test_db):
    """Every test uses the test database, never the demo one (ignores DATABASE_URL from .env/env)."""
    from docs_agent.config import get_settings

    monkeypatch.setenv("DATABASE_URL", _test_database_url())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings_factory():
    def make(**overrides) -> Settings:
        return Settings(_env_file=None, **overrides)

    return make


@pytest.fixture
def db_conn():
    import psycopg

    from docs_agent.db import connect

    assert_not_demo_db(_test_database_url())
    try:
        conn = connect()
    except psycopg.OperationalError:
        pytest.skip("Postgres not available")
    try:
        conn.execute("TRUNCATE chunks, sections, token_usage")
        conn.commit()
        yield conn
        conn.rollback()
        conn.execute("TRUNCATE chunks, sections, token_usage")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_corpus(db_conn):
    from docs_agent.ingest.chunk import Chunk, Section
    from docs_agent.ingest.store import replace_corpus
    from tests.fakes import FakeOpenAI

    chunks = [
        Chunk("https://fastapi.tiangolo.com/tutorial/body/#request-body", "Body > Request Body",
              "Declare a request body with a Pydantic model.", 8),
        Chunk("https://fastapi.tiangolo.com/tutorial/query-params/", "Query Parameters",
              "Query parameters are the key-value pairs after the ? in a URL.", 12),
    ]
    sections = [
        Section("https://fastapi.tiangolo.com/tutorial/body/", "Request Body",
                "# Request Body\n\nWhen you need to send data from a client to your API, you send it as a request body."),
        Section("https://fastapi.tiangolo.com/tutorial/body/#request-body", "Body > Request Body",
                "## Request Body { #request-body }\n\nDeclare a request body with a Pydantic model."),
        Section("https://fastapi.tiangolo.com/tutorial/body/#import-pydantics-basemodel",
                "Request Body > Import Pydantic's BaseModel",
                "## Import Pydantic's `BaseModel` { #import-pydantics-basemodel }\n\nImport `BaseModel` from `pydantic`."),
        Section("https://fastapi.tiangolo.com/tutorial/query-params/", "Query Parameters",
                "# Query Parameters\n\nQuery parameters are the key-value pairs after the ? in a URL."),
    ]
    replace_corpus(db_conn, "test-ref", chunks, [FakeOpenAI.vector_for(c.content) for c in chunks], sections)


class InProcessDocsTools:
    """`get_docs_tools` de los tests de `/ask`: las herramientas puras de `tools.py` en proceso contra `db_conn`.

    Imita lo que hace el servidor MCP lanzado por la API (scope `ask`): los errores esperados llegan al grafo
    como `DocsToolError` con el mensaje del error, igual que por MCP.
    """

    def __init__(self, conn, openai_client, settings):
        self.conn = conn
        self.openai = openai_client
        self.settings = settings.model_copy(update={"mcp_budget_scope": "ask"})
        self.calls: list[tuple[str, dict]] = []

    async def call(self, tool: str, args: dict) -> dict:
        import openai

        from docs_agent.agent.mcp_client import DocsToolError
        from docs_agent.budget import BudgetExceeded
        from docs_agent.mcp_server import tools

        self.calls.append((tool, args))
        try:
            if tool == "search_docs":
                return tools.search_docs(self.conn, self.openai, self.settings, args["query"], args.get("k", 5))
            if tool == "get_section":
                return tools.get_section(self.conn, self.settings, args["url"])
            if tool == "list_sources":
                return tools.list_sources(self.conn, self.settings)
        except (LookupError, BudgetExceeded) as exc:
            raise DocsToolError(str(exc)) from exc
        except openai.OpenAIError as exc:
            raise DocsToolError("Upstream model error") from exc
        raise DocsToolError(f"Unknown tool: {tool}")


# Los vectores de `FakeOpenAI` son aleatorios por hash: una pregunta distinta del texto de un fragmento queda a
# distancia ~1.0. Los tests de `/ask` heredados (semana 1) no fijan umbral, así que por defecto se abre para que
# sigan yendo por la ruta `answer`; los que prueban el umbral real (D21) lo pasan explícito.
OPEN_THRESHOLD = 2.0


def _make_client(db_conn, fake, monkeypatch, tools=None, **settings_overrides):
    from fastapi.testclient import TestClient

    from docs_agent import api
    from docs_agent.api import app, get_conn, get_docs_tools, get_openai
    from docs_agent.config import Settings

    overrides = {
        "openai_api_key": "sk-test",
        "fastapi_docs_ref": "test-ref",
        "no_answer_distance_threshold": OPEN_THRESHOLD,
        **settings_overrides,
    }
    settings = Settings(_env_file=None, **overrides)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    docs_tools = tools if tools is not None else InProcessDocsTools(db_conn, fake, settings)
    app.dependency_overrides[get_conn] = lambda: db_conn
    app.dependency_overrides[get_openai] = lambda: fake
    app.dependency_overrides[get_docs_tools] = lambda: docs_tools
    return TestClient(app)


@pytest.fixture
def client(db_conn, monkeypatch):
    from docs_agent.api import app
    from tests.fakes import FakeOpenAI

    yield _make_client(db_conn, FakeOpenAI(), monkeypatch)
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_failing_openai(db_conn, monkeypatch):
    from docs_agent.api import app
    from tests.fakes import FakeOpenAI

    yield _make_client(db_conn, FakeOpenAI(fail=True), monkeypatch)
    app.dependency_overrides.clear()


@pytest.fixture
def make_client(db_conn, monkeypatch):
    from docs_agent.api import app

    def make(fake, tools=None, **settings_overrides):
        return _make_client(db_conn, fake, monkeypatch, tools=tools, **settings_overrides)

    yield make
    app.dependency_overrides.clear()
