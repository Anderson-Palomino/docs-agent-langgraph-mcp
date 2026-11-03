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
