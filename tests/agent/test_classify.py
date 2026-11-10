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
