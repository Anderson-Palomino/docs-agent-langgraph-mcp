"""Clasificador de dominio: ¿la pregunta es sobre FastAPI? y ¿en qué idioma está? (D31)."""

from typing import Literal

from pydantic import BaseModel

CLASSIFIER_PROMPT = (
    "You classify questions for an assistant that only answers from the FastAPI documentation.\n"
    "- `is_fastapi` is true if the question is about FastAPI or about something its documentation covers: "
    "Pydantic models used in FastAPI, Starlette, security/OAuth2, deployment, Python type hints for APIs.\n"
    "- Any other framework or topic (Django, Flask, general programming unrelated to FastAPI, "
    "non-technical questions) -> `is_fastapi` is false.\n"
    "- `language` is the language of the question: \"es\" for Spanish, \"en\" for English; "
    "any other language -> \"en\".\n"
    "- `reason`: one short sentence explaining the decision."
)


class Classification(BaseModel):
    is_fastapi: bool
    language: Literal["es", "en"]
    reason: str


def classify_question(client, question: str, model: str) -> tuple[Classification, int, int]:
    """Devuelve `(clasificación, prompt_tokens, completion_tokens)`."""
    resp = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": CLASSIFIER_PROMPT},
            {"role": "user", "content": question},
        ],
        response_format=Classification,
        temperature=0,
    )
    message = resp.choices[0].message
    parsed = message.parsed
    if parsed is None:  # rechazo del modelo: tratar como fuera de dominio, en inglés
        parsed = Classification(is_fastapi=False, language="en", reason=message.refusal or "refused")
    return parsed, resp.usage.prompt_tokens, resp.usage.completion_tokens
