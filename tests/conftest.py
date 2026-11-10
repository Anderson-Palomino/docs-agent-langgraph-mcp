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
        conn.execute("TRUNCATE chunks, token_usage")
        conn.commit()
        yield conn
        conn.rollback()
        conn.execute("TRUNCATE chunks, token_usage")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_corpus(db_conn):
    from docs_agent.ingest.chunk import Chunk
    from docs_agent.ingest.store import replace_corpus
    from tests.fakes import FakeOpenAI

    chunks = [
        Chunk("https://fastapi.tiangolo.com/tutorial/body/#request-body", "Body > Request Body",
              "Declare a request body with a Pydantic model.", 8),
        Chunk("https://fastapi.tiangolo.com/tutorial/query-params/", "Query Parameters",
              "Query parameters are the key-value pairs after the ? in a URL.", 12),
    ]
    replace_corpus(db_conn, "test-ref", chunks, [FakeOpenAI.vector_for(c.content) for c in chunks])


def _make_client(db_conn, fake, monkeypatch, **settings_overrides):
    from fastapi.testclient import TestClient

    from docs_agent import api
    from docs_agent.api import app, get_conn, get_openai
    from docs_agent.config import Settings

    overrides = {"openai_api_key": "sk-test", "fastapi_docs_ref": "test-ref", **settings_overrides}
    settings = Settings(_env_file=None, **overrides)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    app.dependency_overrides[get_conn] = lambda: db_conn
    app.dependency_overrides[get_openai] = lambda: fake
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

    def make(fake, **settings_overrides):
        return _make_client(db_conn, fake, monkeypatch, **settings_overrides)

    yield make
    app.dependency_overrides.clear()
