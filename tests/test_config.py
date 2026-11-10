from docs_agent.config import Settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("TOP_K", raising=False)
    s = Settings(_env_file=None)
    assert s.top_k == 5
    assert s.chat_model == "gpt-4.1-mini"
    assert s.embedding_model == "text-embedding-3-small"
    assert "127.0.0.1:5434" in s.database_url


def test_env_override(monkeypatch):
    monkeypatch.setenv("ASK_DAILY_TOKEN_BUDGET", "123")
    assert Settings(_env_file=None).ask_daily_token_budget == 123


def test_settings_repr_hides_api_key():
    from docs_agent.config import Settings

    s = Settings(_env_file=None, openai_api_key="sk-secret")
    assert "sk-secret" not in repr(s)
    assert s.openai_api_key.get_secret_value() == "sk-secret"
