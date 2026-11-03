import pytest

pytestmark = pytest.mark.integration


def test_vector_extension_and_tables(db_conn):
    rows = db_conn.execute("select extname from pg_extension where extname='vector'").fetchall()
    assert rows
    tables = {r[0] for r in db_conn.execute(
        "select tablename from pg_tables where schemaname='public'")}
    assert {"chunks", "token_usage"} <= tables


def test_embedding_dimension_is_1536(db_conn):
    dim = db_conn.execute(
        "select atttypmod from pg_attribute where attrelid='chunks'::regclass and attname='embedding'"
    ).fetchone()[0]
    assert dim == 1536
