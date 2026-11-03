import pytest

from docs_agent.budget import KIND_ASK, record_usage, tokens_used_today

pytestmark = pytest.mark.integration


def test_ask_happy_path(client, seeded_corpus):
    r = client.post("/ask", json={"question": "How do I declare a body?"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True and body["citations"][0]["url"].startswith("https://fastapi.tiangolo.com/")
    assert set(body["usage"]) == {"embedding_tokens", "prompt_tokens", "completion_tokens"}
    assert "retrieved" not in body


@pytest.mark.parametrize("q", ["", "   ", "x" * 1001])
def test_ask_rejects_bad_question(client, q):
    assert client.post("/ask", json={"question": q}).status_code == 422


def test_ask_empty_corpus_503(client):
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and "ingest" in r.json()["detail"]


def test_ask_budget_exhausted_429(client, seeded_corpus, db_conn, settings_factory):
    record_usage(db_conn, KIND_ASK, 10**9)
    r = client.post("/ask", json={"question": "hi"})
    assert r.status_code == 429 and r.json()["detail"] == "Daily token budget exhausted"


def test_ask_upstream_error_502_and_no_usage(client_with_failing_openai, seeded_corpus, db_conn):
    r = client_with_failing_openai.post("/ask", json={"question": "hi"})
    assert r.status_code == 502 and r.json()["detail"] == "Upstream model error"
    assert tokens_used_today(db_conn, KIND_ASK) == 0


def test_ask_records_usage(client, seeded_corpus, db_conn):
    client.post("/ask", json={"question": "hi"})
    assert tokens_used_today(db_conn, KIND_ASK) > 0


def test_debug_includes_retrieved(client, seeded_corpus):
    assert client.post("/ask?debug=true", json={"question": "hi"}).json()["retrieved"]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_ask_and_health_only_see_configured_docs_version(make_client, db_conn):
    from docs_agent.ingest.chunk import Chunk
    from docs_agent.ingest.store import replace_corpus
    from tests.fakes import FakeOpenAI

    old = Chunk("https://fastapi.tiangolo.com/old/", "Old", "old docs version", 3)
    new = Chunk("https://fastapi.tiangolo.com/new/", "New", "new docs version", 3)
    replace_corpus(db_conn, "old-ref", [old], [FakeOpenAI.vector_for(old.content)])
    replace_corpus(db_conn, "test-ref", [new], [FakeOpenAI.vector_for(new.content)])
    c = make_client(FakeOpenAI())
    body = c.post("/ask?debug=true", json={"question": "docs"}).json()
    assert [r["url"] for r in body["retrieved"]] == [new.url]
    assert c.get("/health").json()["chunks"] == 1


def test_ask_chat_only_non_api_error_502_and_no_usage(make_client, seeded_corpus, db_conn):
    from tests.fakes import FakeOpenAI

    c = make_client(FakeOpenAI(fail_chat=True))
    r = c.post("/ask", json={"question": "hi"})
    assert r.status_code == 502 and r.json()["detail"] == "Upstream model error"
    assert tokens_used_today(db_conn, KIND_ASK) == 0


def test_ask_without_api_key_503(make_client, seeded_corpus):
    from tests.fakes import FakeOpenAI

    fake = FakeOpenAI()
    r = make_client(fake, openai_api_key="").post("/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json()["detail"] == "OPENAI_API_KEY not configured"
    assert fake.calls == []


def test_openai_client_has_timeout_and_retries(monkeypatch):
    from docs_agent import api
    from docs_agent.config import Settings

    monkeypatch.setattr(api, "get_settings", lambda: Settings(_env_file=None, openai_api_key="sk-test"))
    client = api.get_openai()
    assert client.timeout == 30 and client.max_retries == 2
