"""Clasificador de dominio: ¿la pregunta es sobre FastAPI?, ¿en qué idioma está? (D31) y, si está en
español, su traducción al inglés para la búsqueda (D40)."""

from typing import Literal

from pydantic import BaseModel

CLASSIFIER_PROMPT = (
    "You classify questions for an assistant that only answers from the FastAPI documentation.\n"
    "- `is_fastapi` is true if the question is about FastAPI or about something its documentation covers: "
    "Pydantic models used in FastAPI, Starlette, security/OAuth2, dependencies, deployment, testing, "
    "Python type hints for APIs. The question does not need to name FastAPI.\n"
    "  Examples (true): \"How do I declare a request body with a Pydantic model?\", "
    "\"How do I add OAuth2 scopes to a path operation?\", \"How do dependencies with yield work?\", "
    "\"How do I test my app with TestClient?\", \"¿Cómo despliego mi app con Docker?\", "
    "\"How do I use a Starlette middleware?\".\n"
    "- Questions about how to use another framework or library (Django, Django REST Framework, Flask, "
    "Express, Spring, ...) are `is_fastapi` false, EVEN IF the FastAPI docs mention or compare it: "
    "mentioned is not documented.\n"
    "  Examples (false): \"How do I write a serializer in Django REST Framework?\", "
    "\"How do I define a Flask blueprint?\", \"How do I add middleware in Express?\".\n"
    "- Any other topic (general programming unrelated to FastAPI, non-technical questions) -> "
    "`is_fastapi` is false.\n"
    "- `language` is the language of the question: \"es\" for Spanish, \"en\" for English; "
    "any other language -> \"en\".\n"
    "- `search_query`: only if `language` is \"es\", the question translated into English as a search query "
    "for the FastAPI documentation. Keep its meaning and do not answer it. Keep code identifiers as they "
    "are, and when the question clearly refers to a FastAPI concept without naming it, use the term the "
    "FastAPI docs use for it (for example \"subir un archivo\" -> `UploadFile`, \"filtrar los campos de la "
    "respuesta\" -> `response_model`). Do not add concepts the question does not ask about. "
    "It is null if `language` is \"en\".\n"
    "- `reason`: one short sentence explaining the decision."
)


class Classification(BaseModel):
    is_fastapi: bool
    language: Literal["es", "en"]
    reason: str
    # Traducción al inglés para la búsqueda (D40). En modo estricto el SDK la marca `required` y quita el
    # default `None`: lo opcional queda como unión con null, como pide la doc de Structured Outputs.
    search_query: str | None = None


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
        parsed = Classification(
            is_fastapi=False, language="en", reason=message.refusal or "refused", search_query=None
        )
    return parsed, resp.usage.prompt_tokens, resp.usage.completion_tokens


def resolve_search_query(question: str, c: Classification) -> tuple[str, bool]:
    """Consulta que se usa en la búsqueda y si es una traducción (D40).

    Solo se usa la traducción si la pregunta es en español y la traducción no queda vacía tras `strip()`;
    en cualquier otro caso (inglés, `None`, vacía) se busca con la pregunta original.
    """
    translation = (c.search_query or "").strip()
    if c.language == "es" and translation:
        return translation, True
    return question, False
