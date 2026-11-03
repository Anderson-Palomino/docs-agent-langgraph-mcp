import pytest

from docs_agent.ingest.chunk import Chunk
from docs_agent.ingest.store import replace_corpus
from docs_agent.rag.retrieve import corpus_size, search

pytestmark = pytest.mark.integration


def unit(i):  # vector one-hot
    v = [0.0] * 1536
    v[i] = 1.0
    return v


def test_search_orders_by_cosine_distance(db_conn):
    chunks = [Chunk(f"https://fastapi.tiangolo.com/p{i}/", f"P{i}", f"c{i}", 1) for i in range(7)]
    replace_corpus(db_conn, "t", chunks, [unit(i) for i in range(7)])
    q = unit(3)
    q[4] = 0.5
    res = search(db_conn, q, k=5)
    assert len(res) == 5
    assert [r.url for r in res[:2]] == [
        "https://fastapi.tiangolo.com/p3/",
        "https://fastapi.tiangolo.com/p4/",
    ]
    assert res[0].distance <= res[1].distance
    assert corpus_size(db_conn) == 7


def test_search_empty_corpus(db_conn):
    assert search(db_conn, unit(0)) == [] and corpus_size(db_conn) == 0
