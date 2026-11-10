import os

import pytest

from docs_agent.tracing import configure_tracing

VARS = ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # setenv registra el valor original para restaurarlo al final, también si no existía:
    # así lo que escriba configure_tracing en os.environ no se filtra a otros tests.
    for v in VARS:
        monkeypatch.setenv(v, "")
        monkeypatch.delenv(v)


def test_tracing_off_by_default(settings_factory):
    assert configure_tracing(settings_factory()) is False
    assert not any(v in os.environ for v in VARS)


def test_tracing_needs_key(settings_factory):
    assert configure_tracing(settings_factory(langsmith_tracing=True)) is False
    assert not any(v in os.environ for v in VARS)


def test_tracing_copies_settings_to_environ(settings_factory, monkeypatch):
    s = settings_factory(langsmith_tracing=True, langsmith_api_key="ls-test", langsmith_project="p1")
    assert configure_tracing(s) is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls-test"
    assert os.environ["LANGSMITH_PROJECT"] == "p1"


def test_tracing_disabled_by_default_leaves_env_untouched():
    """Sin settings explícitos (lo que hace la API al arrancar): nada de LANGSMITH_* en el entorno."""
    from docs_agent.config import Settings

    assert configure_tracing(Settings(_env_file=None)) is False
    assert "LANGSMITH_TRACING" not in os.environ


def test_tracing_enabled_sets_env(settings_factory):
    assert configure_tracing(settings_factory(langsmith_tracing=True, langsmith_api_key="ls-test")) is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "docs-agent"


def _lifespan_settings(monkeypatch, **overrides):
    from docs_agent import api
    from docs_agent.config import Settings

    settings = Settings(_env_file=None, openai_api_key="sk-test", **overrides)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    return settings


def test_api_startup_without_tracing_does_not_wrap_openai(monkeypatch):
    from fastapi.testclient import TestClient

    from docs_agent import api

    _lifespan_settings(monkeypatch)
    with TestClient(api.app):
        assert api.app.state.tracing is False
        assert "LANGSMITH_TRACING" not in os.environ
        client = api.make_openai(api.app.state.tracing)
        assert not hasattr(client.chat.completions.parse, "__wrapped__")  # cliente OpenAI tal cual


def test_api_startup_with_tracing_wraps_openai(monkeypatch):
    """Con tracing, la API llama a configure_tracing al arrancar y envuelve el cliente con `wrap_openai`
    (clasificador y respuesta quedan como corridas LLM hijas, con tokens). No se hace ninguna llamada:
    ni OpenAI ni LangSmith reciben nada."""
    from fastapi.testclient import TestClient

    from docs_agent import api

    _lifespan_settings(monkeypatch, langsmith_tracing=True, langsmith_api_key="ls-test", langsmith_project="p1")
    with TestClient(api.app):
        assert api.app.state.tracing is True
        assert os.environ["LANGSMITH_TRACING"] == "true" and os.environ["LANGSMITH_PROJECT"] == "p1"
        client = api.make_openai(api.app.state.tracing)
        assert hasattr(client.chat.completions.parse, "__wrapped__")  # functools.wraps de wrap_openai
        assert client.timeout == 30 and client.max_retries == 2


def test_ask_runs_graph_with_run_name_and_question_metadata(client, seeded_corpus, monkeypatch):
    """La corrida del grafo se llama `ask` y lleva la pregunta en metadata; route/reason salen en las outputs."""
    from docs_agent import api

    seen: list[dict] = []
    real_build = api.build_graph

    def spy_build(deps):
        graph = real_build(deps)
        real_ainvoke = graph.ainvoke

        async def ainvoke(inp, config=None, **kw):
            seen.append(config)
            return await real_ainvoke(inp, config=config, **kw)

        graph.ainvoke = ainvoke
        return graph

    monkeypatch.setattr(api, "build_graph", spy_build)
    r = client.post("/ask", json={"question": "How do I declare a body?"})
    assert r.status_code == 200
    assert seen == [{"run_name": "ask", "metadata": {"question": "How do I declare a body?"}}]


def test_ask_works_without_tracing(client, seeded_corpus, recwarn):
    r = client.post("/ask", json={"question": "How do I declare a body?"})
    assert r.status_code == 200 and r.json()["route"] == "answer"
    assert not [w for w in recwarn if "langsmith" in f"{w.filename} {w.message}".lower()]
