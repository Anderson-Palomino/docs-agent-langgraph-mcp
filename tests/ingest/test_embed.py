import math

from docs_agent.ingest.embed import embed_texts
from tests.fakes import EMBEDDING_DIM, FakeOpenAI


def test_embed_batches_and_preserves_order():
    fake = FakeOpenAI()
    vecs, tokens = embed_texts(fake, [f"t{i}" for i in range(250)], model="m", batch_size=100)
    assert len(vecs) == 250 and len(fake.calls) == 3
    assert vecs[0] == fake.vector_for("t0") and tokens > 0
    assert vecs[249] == fake.vector_for("t249")
    assert [len(c["input"]) for c in fake.calls] == [100, 100, 50]
    assert all(c["model"] == "m" for c in fake.calls)


def test_embed_empty_makes_no_calls():
    fake = FakeOpenAI()
    assert embed_texts(fake, [], model="m") == ([], 0)
    assert fake.calls == []


def test_fake_vectors_are_1536d_normalized_and_deterministic():
    v = FakeOpenAI.vector_for("x")
    assert len(v) == EMBEDDING_DIM
    assert math.isclose(math.sqrt(sum(a * a for a in v)), 1.0, rel_tol=1e-9)
    assert v == FakeOpenAI.vector_for("x") and v != FakeOpenAI.vector_for("y")
