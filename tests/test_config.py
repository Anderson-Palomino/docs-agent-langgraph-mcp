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


def test_settings_repr_hides_langsmith_key():
    s = Settings(_env_file=None, langsmith_api_key="lsv2-secret")
    assert "lsv2-secret" not in repr(s) and "lsv2-secret" not in str(s)
    assert s.langsmith_api_key.get_secret_value() == "lsv2-secret"


def test_threshold_setting_from_env(monkeypatch):
    monkeypatch.setenv("NO_ANSWER_DISTANCE_THRESHOLD", "0.5")
    assert Settings(_env_file=None).no_answer_distance_threshold == 0.5
