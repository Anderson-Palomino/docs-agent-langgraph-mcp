from docs_agent.config import Settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("TOP_K", raising=False)
    s = Settings(_env_file=None)
    assert s.top_k == 5
    assert s.chat_model == "gpt-4.1-mini"
    assert s.embedding_model == "text-embedding-3-small"
    assert "localhost:5434" in s.database_url


def test_env_override(monkeypatch):
    monkeypatch.setenv("ASK_DAILY_TOKEN_BUDGET", "123")
    assert Settings(_env_file=None).ask_daily_token_budget == 123
