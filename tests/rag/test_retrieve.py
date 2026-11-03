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
    res = search(db_conn, q, "t", k=5)
    assert len(res) == 5
    assert [r.url for r in res[:2]] == [
        "https://fastapi.tiangolo.com/p3/",
        "https://fastapi.tiangolo.com/p4/",
    ]
    assert res[0].distance <= res[1].distance
    assert corpus_size(db_conn, "t") == 7


def test_search_empty_corpus(db_conn):
    assert search(db_conn, unit(0), "t") == [] and corpus_size(db_conn, "t") == 0


def test_search_and_count_are_scoped_to_source_ref(db_conn):
    a = [Chunk(f"https://fastapi.tiangolo.com/a{i}/", f"A{i}", f"a{i}", 1) for i in range(3)]
    b = [Chunk(f"https://fastapi.tiangolo.com/b{i}/", f"B{i}", f"b{i}", 1) for i in range(2)]
    replace_corpus(db_conn, "v1", a, [unit(i) for i in range(3)])
    replace_corpus(db_conn, "v2", b, [unit(0), unit(5)])  # b0 is identical to a0 for the query
    res = search(db_conn, unit(0), "v2", k=5)
    assert {r.url for r in res} == {c.url for c in b}
    assert corpus_size(db_conn, "v1") == 3 and corpus_size(db_conn, "v2") == 2
    assert corpus_size(db_conn, "other") == 0 and search(db_conn, unit(0), "other") == []
