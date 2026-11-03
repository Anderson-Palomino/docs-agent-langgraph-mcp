import pytest

from docs_agent.budget import KIND_INGEST, tokens_used_today
from docs_agent.ingest.fetch import DocFile
from docs_agent.ingest.run import IngestLimitExceeded, main, run_ingest
from tests.fakes import FakeOpenAI

pytestmark = pytest.mark.integration

DOCS = [
    DocFile("a.md", "https://fastapi.tiangolo.com/a/", "# A\n\nIntro text.\n\n## One\n\nBody one.\n"),
    DocFile("b.md", "https://fastapi.tiangolo.com/b/", "# B\n\nOther page.\n\n## Two\n\nBody two.\n"),
]


@pytest.fixture(autouse=True)
def _fake_fetch(monkeypatch):
    monkeypatch.setattr("docs_agent.ingest.run.fetch_docs", lambda ref, **kw: DOCS)


def test_run_ingest_aborts_over_limit_without_calling_openai(db_conn, settings_factory):
    fake = FakeOpenAI()
    with pytest.raises(IngestLimitExceeded):
        run_ingest(settings_factory(ingest_max_tokens=1), fake, db_conn)
    assert fake.calls == []
    assert db_conn.execute("select count(*) from chunks").fetchone()[0] == 0


def test_run_ingest_stores_and_records_usage(db_conn, settings_factory):
    settings = settings_factory()
    n = run_ingest(settings, FakeOpenAI(), db_conn)
    assert n > 0
    assert db_conn.execute("select count(*) from chunks").fetchone()[0] == n
    assert tokens_used_today(db_conn, KIND_INGEST) > 0
    refs = db_conn.execute("select distinct source_ref from chunks").fetchall()
    assert refs == [(settings.fastapi_docs_ref,)]


def test_main_exits_1_without_api_key(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from docs_agent.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit) as exc:
            main()
    finally:
        get_settings.cache_clear()
    assert exc.value.code == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
