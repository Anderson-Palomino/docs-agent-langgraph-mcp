from pathlib import Path

import pytest
from pydantic import ValidationError

from docs_agent.budget import BudgetExceeded, record_usage, tokens_used_today
from docs_agent.config import Settings
from docs_agent.mcp_server.tools import NOT_IN_CORPUS_NOTICE, get_section, list_sources, search_docs
from tests.fakes import FakeOpenAI

REPO = Path(__file__).resolve().parents[2]
BODY = "https://fastapi.tiangolo.com/tutorial/body/"


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{"openai_api_key": "sk-test", "fastapi_docs_ref": "test-ref", **overrides})


def test_invalid_budget_scope_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mcp_budget_scope="x")


def test_budget_scope_defaults():
    s = Settings(_env_file=None)
    assert s.mcp_budget_scope == "mcp"
    assert s.mcp_daily_token_budget == 100_000


@pytest.mark.integration
def test_list_sources_counts(seeded_corpus, db_conn):
    assert list_sources(db_conn, make_settings()) == {
        "project": "FastAPI",
        "version": "test-ref",
        "pages": 2,
        "chunks": 2,
        "sections": 4,
    }


@pytest.mark.integration
def test_search_docs_shape_and_in_corpus_true(seeded_corpus, db_conn):
    query = "Declare a request body with a Pydantic model."
    out = search_docs(db_conn, FakeOpenAI(), make_settings(), query, k=5)
    assert set(out) == {"results", "best_distance", "in_corpus", "notice", "embedding_tokens"}
    assert len(out["results"]) == 2
    first = out["results"][0]
    assert set(first) == {"title", "url", "distance", "snippet"}
    assert first["url"] == f"{BODY}#request-body"
    assert first["snippet"] == query
    assert out["best_distance"] == pytest.approx(0.0, abs=1e-6)
    assert out["in_corpus"] is True
    assert out["notice"] is None
    assert out["embedding_tokens"] > 0


@pytest.mark.integration
def test_search_docs_snippet_is_first_300_chars(db_conn):
    from docs_agent.ingest.chunk import Chunk
    from docs_agent.ingest.store import replace_corpus

    content = "x" * 500
    replace_corpus(db_conn, "test-ref", [Chunk(BODY, "Body", content, 1)], [FakeOpenAI.vector_for(content)])
    out = search_docs(db_conn, FakeOpenAI(), make_settings(), content)
    assert out["results"][0]["snippet"] == "x" * 300


@pytest.mark.integration
def test_search_docs_include_content_adds_full_chunk(db_conn):
    from docs_agent.ingest.chunk import Chunk
    from docs_agent.ingest.store import replace_corpus

    content = "x" * 500
    replace_corpus(db_conn, "test-ref", [Chunk(BODY, "Body", content, 1)], [FakeOpenAI.vector_for(content)])
    default = search_docs(db_conn, FakeOpenAI(), make_settings(), content)
    assert "content" not in default["results"][0]
    full = search_docs(db_conn, FakeOpenAI(), make_settings(), content, include_content=True)
    first = full["results"][0]
    assert set(first) == {"title", "url", "distance", "snippet", "content"}
    assert first["content"] == content and first["snippet"] == "x" * 300


@pytest.mark.integration
@pytest.mark.parametrize("k, expected", [(0, 1), (-3, 1), (1, 1), (50, 2)])
def test_search_docs_clamps_k(seeded_corpus, db_conn, k, expected):
    out = search_docs(db_conn, FakeOpenAI(), make_settings(), "anything", k=k)
    assert len(out["results"]) == expected


@pytest.mark.integration
def test_search_docs_out_of_corpus_sets_notice(seeded_corpus, db_conn):
    settings = make_settings(no_answer_distance_threshold=0.0001)
    out = search_docs(db_conn, FakeOpenAI(), settings, "How do I configure the Django ORM?")
    assert out["in_corpus"] is False
    assert out["notice"] == NOT_IN_CORPUS_NOTICE
    assert NOT_IN_CORPUS_NOTICE == (
        "No relevant section in the indexed FastAPI docs. Do not answer from general knowledge."
    )
    assert out["results"]  # los resultados se devuelven igual; decide el cliente


@pytest.mark.integration
def test_search_docs_empty_corpus(db_conn):
    out = search_docs(db_conn, FakeOpenAI(), make_settings(), "request body")
    assert out["results"] == []
    assert out["best_distance"] is None
    assert out["in_corpus"] is False
    assert out["notice"] == NOT_IN_CORPUS_NOTICE


@pytest.mark.integration
@pytest.mark.parametrize("scope, other", [("mcp", "ask"), ("ask", "mcp")])
def test_search_docs_records_usage_under_scope(seeded_corpus, db_conn, scope, other):
    search_docs(db_conn, FakeOpenAI(), make_settings(mcp_budget_scope=scope), "request body")
    assert tokens_used_today(db_conn, scope) > 0
    assert tokens_used_today(db_conn, other) == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    "scope, limit_field",
    [("mcp", "mcp_daily_token_budget"), ("ask", "ask_daily_token_budget")],
)
def test_search_docs_budget_exhausted_raises(seeded_corpus, db_conn, scope, limit_field):
    settings = make_settings(mcp_budget_scope=scope, **{limit_field: 10})
    record_usage(db_conn, scope, 10)
    fake = FakeOpenAI()
    with pytest.raises(BudgetExceeded):
        search_docs(db_conn, fake, settings, "request body")
    assert fake.calls == []  # con el presupuesto agotado no se llama a OpenAI


@pytest.mark.integration
def test_get_section_returns_section_without_attr_suffix(seeded_corpus, db_conn):
    out = get_section(db_conn, make_settings(), f"  {BODY}#request-body \n")
    assert out == {
        "url": f"{BODY}#request-body",
        "title": "Body > Request Body",
        "content": "## Request Body\n\nDeclare a request body with a Pydantic model.",
    }


@pytest.mark.integration
def test_get_section_unknown_url_error_mentions_search_docs(seeded_corpus, db_conn):
    url = f"{BODY}#nope"
    with pytest.raises(LookupError) as exc:
        get_section(db_conn, make_settings(), url)
    assert str(exc.value) == f"Unknown section URL: {url}. Use search_docs to find valid URLs."


@pytest.mark.integration
def test_get_section_other_version_is_unknown(seeded_corpus, db_conn):
    with pytest.raises(LookupError):
        get_section(db_conn, make_settings(fastapi_docs_ref="other-ref"), f"{BODY}#request-body")


@pytest.mark.integration
def test_get_section_page_url_lists_sections(seeded_corpus, db_conn):
    out = get_section(db_conn, make_settings(), BODY)
    assert out["url"] == BODY
    assert out["title"] == "Request Body"
    assert out["content"].startswith("# Request Body\n\nWhen you need to send data")
    assert out["sections"] == [
        {"title": "Body > Request Body", "url": f"{BODY}#request-body"},
        {"title": "Request Body > Import Pydantic's BaseModel", "url": f"{BODY}#import-pydantics-basemodel"},
    ]


@pytest.mark.integration
def test_get_section_oauth2_has_real_code(db_conn):
    """Pedido por el dueño: la sección que define get_current_user trae el código real, no el include."""
    from docs_agent.ingest.chunk import split_sections
    from docs_agent.ingest.fetch import fetch_docs
    from docs_agent.ingest.store import replace_corpus

    ref = "0.162.0"
    if not (REPO / "data" / f"fastapi-{ref}.tar.gz").exists():
        pytest.skip("cached FastAPI tarball not available")
    docs = fetch_docs(ref, cache_dir=REPO / "data")
    page = next(d for d in docs if d.rel_path == "tutorial/security/get-current-user.md")
    sections = split_sections(page)
    replace_corpus(db_conn, ref, [], [], sections)
    url = "https://fastapi.tiangolo.com/tutorial/security/get-current-user/#create-a-get-current-user-dependency"

    out = get_section(db_conn, make_settings(fastapi_docs_ref=ref), url)
    assert out["url"] == url
    assert out["content"].startswith("## Create a `get_current_user` dependency\n")
    assert "OAuth2PasswordBearer" in out["content"]
    assert "def get_current_user" in out["content"]  # cubre también `async def get_current_user`
    assert "{*" not in out["content"]


@pytest.mark.integration
def test_search_docs_records_usage_even_if_search_fails(seeded_corpus, db_conn, monkeypatch):
    from docs_agent.mcp_server import tools

    def boom(*args, **kwargs):
        raise RuntimeError("search failed")

    monkeypatch.setattr(tools, "search", boom)
    with pytest.raises(RuntimeError):
        search_docs(db_conn, FakeOpenAI(), make_settings(), "request body")
    db_conn.rollback()
    assert tokens_used_today(db_conn, "mcp") > 0


@pytest.mark.parametrize("k, expected", [(-1, 1), (0, 1), (5, 5), (10, 10), (11, 10)])
def test_clamp_k(k, expected):
    from docs_agent.mcp_server.tools import clamp_k

    assert clamp_k(k) == expected
