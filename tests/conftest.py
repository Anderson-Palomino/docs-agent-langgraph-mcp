import pytest

from docs_agent.config import Settings


@pytest.fixture
def settings_factory():
    def make(**overrides) -> Settings:
        return Settings(_env_file=None, **overrides)

    return make


@pytest.fixture
def db_conn():
    import psycopg

    from docs_agent.db import connect

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


def _make_client(db_conn, fake):
    from fastapi.testclient import TestClient

    from docs_agent.api import app, get_conn, get_openai

    app.dependency_overrides[get_conn] = lambda: db_conn
    app.dependency_overrides[get_openai] = lambda: fake
    return TestClient(app)


@pytest.fixture
def client(db_conn):
    from docs_agent.api import app
    from tests.fakes import FakeOpenAI

    yield _make_client(db_conn, FakeOpenAI())
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_failing_openai(db_conn):
    from docs_agent.api import app
    from tests.fakes import FakeOpenAI

    yield _make_client(db_conn, FakeOpenAI(fail=True))
    app.dependency_overrides.clear()
