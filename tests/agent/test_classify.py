import pydantic
import pytest

from docs_agent.agent.classify import Classification, classify_question
from tests.fakes import FakeOpenAI


def test_classification_schema_has_language():
    assert {"is_fastapi", "language", "reason"} <= set(Classification.model_fields)
    assert Classification(is_fastapi=True, language="es", reason="r").language == "es"
    with pytest.raises(pydantic.ValidationError):
        Classification(is_fastapi=True, language="fr", reason="r")


def test_prompt_rejects_other_frameworks_even_if_mentioned():
    from docs_agent.agent.classify import CLASSIFIER_PROMPT

    assert "Django REST Framework" in CLASSIFIER_PROMPT
    assert "mentioned is not documented" in CLASSIFIER_PROMPT
    assert "EVEN IF the FastAPI docs mention or compare it" in CLASSIFIER_PROMPT
    for positive in ("Pydantic", "Starlette", "OAuth2", "dependencies", "deployment", "testing"):
        assert positive in CLASSIFIER_PROMPT


def test_classify_question_uses_schema_temperature_zero_and_returns_usage():
    fake = FakeOpenAI(is_fastapi=False, language="es")
    c, prompt_tokens, completion_tokens = classify_question(fake, "¿Cómo uso Django?", model="m")
    assert c.is_fastapi is False and c.language == "es"
    assert (prompt_tokens, completion_tokens) == (100, 20)
    call = fake.calls[0]
    assert call["model"] == "m" and call["temperature"] == 0
    assert call["messages"][-1]["content"] == "¿Cómo uso Django?"
    assert "FastAPI" in call["messages"][0]["content"]


def test_classification_schema_has_search_query():
    schema = Classification.model_json_schema()
    types = {t.get("type") for t in schema["properties"]["search_query"]["anyOf"]}
    assert types == {"string", "null"}
    # Modo estricto de OpenAI: el SDK marca todos los campos como `required`; lo opcional es la unión con null.
    from openai.lib._pydantic import to_strict_json_schema

    strict = to_strict_json_schema(Classification)
    assert "search_query" in strict["required"]
    assert "default" not in strict["properties"]["search_query"]


def test_prompt_asks_for_english_search_query_only_for_spanish():
    from docs_agent.agent.classify import CLASSIFIER_PROMPT

    assert "`search_query`" in CLASSIFIER_PROMPT
    assert "translated into English" in CLASSIFIER_PROMPT
    assert 'only if `language` is "es"' in CLASSIFIER_PROMPT
    assert 'null if `language` is "en"' in CLASSIFIER_PROMPT
    assert "do not answer" in CLASSIFIER_PROMPT and "do not expand" in CLASSIFIER_PROMPT
    for identifier in ("`Depends`", "`status_code`", "`Query`"):
        assert identifier in CLASSIFIER_PROMPT


def _c(language: str, search_query):
    return Classification(is_fastapi=True, language=language, reason="r", search_query=search_query)


def test_resolve_search_query_uses_spanish_translation():
    from docs_agent.agent.classify import resolve_search_query

    assert resolve_search_query("¿Cómo…?", _c("es", "How…?")) == ("How…?", True)
    assert resolve_search_query("¿Cómo…?", _c("es", "  How…?\n")) == ("How…?", True)


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_resolve_search_query_empty_translation_falls_back(empty):
    from docs_agent.agent.classify import resolve_search_query

    assert resolve_search_query("¿Cómo…?", _c("es", empty)) == ("¿Cómo…?", False)


def test_resolve_search_query_ignores_translation_for_english():
    from docs_agent.agent.classify import resolve_search_query

    assert resolve_search_query("How…?", _c("en", "Otra cosa")) == ("How…?", False)


def test_refusal_has_no_translation():
    from types import SimpleNamespace

    message = SimpleNamespace(parsed=None, refusal="nope")
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2)
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                parse=lambda **_: SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)
            )
        )
    )
    c, _, _ = classify_question(client, "¿Cómo…?", model="m")
    assert c == Classification(is_fastapi=False, language="en", reason="nope", search_query=None)
