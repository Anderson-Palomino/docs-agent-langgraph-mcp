from docs_agent.config import get_settings


def test_tests_never_point_at_demo_db():
    assert get_settings().database_url.endswith("/docs_test")


def test_db_conn_uses_test_database(db_conn):
    assert db_conn.execute("select current_database()").fetchone()[0] == "docs_test"


def test_guard_refuses_demo_db():
    import pytest

    from tests.conftest import assert_not_demo_db

    assert_not_demo_db("postgresql://docs:docs@127.0.0.1:5434/docs_test")
    with pytest.raises(pytest.exit.Exception):
        assert_not_demo_db("postgresql://docs:docs@127.0.0.1:5434/docs")
