"""Respuesta con salida estructurada y citas validadas contra los fragmentos recuperados."""

from dataclasses import dataclass

from pydantic import BaseModel

from docs_agent.rag.retrieve import RetrievedChunk

SYSTEM_PROMPT = (
    "You answer questions about the FastAPI documentation.\n"
    "- Answer ONLY with the information in the numbered context fragments provided.\n"
    "- Reply in the same language as the user's question.\n"
    "- In `citations`, list the exact URLs (copied verbatim) of the fragments you actually used.\n"
    "- If the context is not enough to answer, say you don't know and leave `citations` empty."
)


class LLMAnswer(BaseModel):
    answer: str
    citations: list[str]


class Citation(BaseModel):
    url: str
    title: str


@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation]
    grounded: bool
    prompt_tokens: int
    completion_tokens: int


def build_messages(question: str, chunks: list[RetrievedChunk], section_text: str | None = None) -> list[dict]:
    """Contexto numerado. Con `section_text`, el fragmento [1] lleva la sección completa de `chunks[0]`
    (misma URL y título) en lugar de su fragmento; el resto de `chunks` va tal cual."""
    contents = [c.content for c in chunks]
    if section_text is not None and chunks:
        contents[0] = section_text
    context = "\n\n".join(
        f"[{i}] {c.title}\nURL: {c.url}\n{text}" for i, (c, text) in enumerate(zip(chunks, contents), start=1)
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {question}"},
    ]


def validate_citations(cited: list[str], chunks: list[RetrievedChunk]) -> list[Citation]:
    """Conserva solo URLs presentes en `chunks`, sin duplicados y en el orden citado."""
    titles: dict[str, str] = {}
    for c in chunks:
        titles.setdefault(c.url, c.title)
    result: list[Citation] = []
    seen: set[str] = set()
    for raw in cited:
        url = raw.strip()
        if url in titles and url not in seen:
            seen.add(url)
            result.append(Citation(url=url, title=titles[url]))
    return result


def answer_question(
    client, question: str, chunks: list[RetrievedChunk], model: str, section_text: str | None = None
) -> AnswerResult:
    """Responde con `chunks` como contexto; las citas se validan siempre contra las URLs de `chunks`."""
    resp = client.chat.completions.parse(
        model=model,
        messages=build_messages(question, chunks, section_text),
        response_format=LLMAnswer,
        temperature=0,
    )
    message = resp.choices[0].message
    parsed = message.parsed
    if parsed is None:  # rechazo del modelo: sin respuesta estructurada
        parsed = LLMAnswer(answer=message.refusal or "", citations=[])
    citations = validate_citations(parsed.citations, chunks)
    return AnswerResult(
        answer=parsed.answer,
        citations=citations,
        grounded=len(citations) > 0,
        prompt_tokens=resp.usage.prompt_tokens,
        completion_tokens=resp.usage.completion_tokens,
    )
