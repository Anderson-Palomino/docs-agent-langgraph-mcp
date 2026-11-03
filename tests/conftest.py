import pytest

from docs_agent.config import Settings


@pytest.fixture
def settings_factory():
    def make(**overrides) -> Settings:
        return Settings(_env_file=None, **overrides)

    return make


@pytest.fixture
def db_conn():
    from docs_agent.db import connect

    try:
        conn = connect()
    except Exception:
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
