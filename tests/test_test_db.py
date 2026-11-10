from docs_agent.config import get_settings


def test_tests_never_point_at_demo_db():
    assert get_settings().database_url.endswith("/docs_test")


def test_db_conn_uses_test_database(db_conn):
    assert db_conn.execute("select current_database()").fetchone()[0] == "docs_test"
