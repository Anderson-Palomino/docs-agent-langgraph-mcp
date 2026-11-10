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
