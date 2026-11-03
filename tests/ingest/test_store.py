import pytest

from docs_agent.budget import KIND_INGEST, tokens_used_today
from docs_agent.db import connect
from docs_agent.ingest.chunk import Chunk
from docs_agent.ingest.store import replace_corpus

pytestmark = pytest.mark.integration

CHUNK = Chunk("https://fastapi.tiangolo.com/a/#x", "A > X", "hello", 1)
VEC = [[1.0] + [0.0] * 1535]


def test_replace_corpus_is_idempotent(db_conn):
    assert replace_corpus(db_conn, "0.1", [CHUNK], VEC) == 1
    assert replace_corpus(db_conn, "0.1", [CHUNK], VEC) == 1
    assert db_conn.execute("select count(*) from chunks").fetchone()[0] == 1


def test_replace_corpus_commits_even_after_an_open_read_transaction(db_conn):
    tokens_used_today(db_conn, KIND_INGEST)  # deja una transacción de lectura abierta
    replace_corpus(db_conn, "0.1", [CHUNK], VEC)
    other = connect()
    try:
        assert other.execute("select count(*) from chunks").fetchone()[0] == 1
    finally:
        other.close()


def test_replace_corpus_only_replaces_same_source_ref(db_conn):
    replace_corpus(db_conn, "0.1", [CHUNK], VEC)
    replace_corpus(db_conn, "0.2", [CHUNK], VEC)
    replace_corpus(db_conn, "0.1", [], [])
    rows = db_conn.execute("select source_ref from chunks").fetchall()
    assert rows == [("0.2",)]


def test_replace_corpus_rolls_back_on_failure(db_conn):
    replace_corpus(db_conn, "0.1", [CHUNK], VEC)
    with pytest.raises(Exception):
        replace_corpus(db_conn, "0.1", [CHUNK], [[1.0, 2.0]])  # dimensión errónea
    assert db_conn.execute("select count(*) from chunks").fetchone()[0] == 1
