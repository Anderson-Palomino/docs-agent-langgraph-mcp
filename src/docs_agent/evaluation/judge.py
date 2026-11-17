"""LLM juez de fidelidad (D38): ¿la respuesta está apoyada solo en el contexto que vio el modelo?"""

from pydantic import BaseModel, Field

from docs_agent.agent.graph import cap_section, chunks_from_results
from docs_agent.rag.answer import build_context

JUDGE_MODEL = "gpt-4.1-mini"  # igual al que responde, nunca más débil

JUDGE_PROMPT = (
    "You are a strict faithfulness judge for a question-answering assistant that must answer ONLY from the "
    "context it was given.\n"
    "You receive the question, the exact context the assistant saw, and the assistant's answer.\n"
    "- Judge ONLY whether each claim in the answer is supported by the context. Do NOT judge whether the "
    "claim is true in the real world: a true claim that the context does not contain is unsupported, and a "
    "claim the context states is supported even if you believe it is wrong.\n"
    "- An answer that honestly says the context does not cover something (for example \"the docs do not say "
    "when\" or \"the docs only show version 0.x\") is NOT penalized when the context indeed does not cover "
    "it. Such statements count as supported.\n"
    "- Any invented detail (a date, a version, a feature, a parameter, a number) that the context does not "
    "contain is unsupported, even if it sounds plausible.\n"
    "- Ignore style, language and formatting; only factual claims count.\n"
    "- `unsupported_claims`: list each unsupported claim, short and verbatim or close to it; empty if none.\n"
    "- `score`: the fraction of the answer's claims that are supported, from 0 to 1 (1 = all supported, "
    "0 = none).\n"
    "- `reason`: one short sentence explaining the score."
)


class Judgment(BaseModel):
    score: float = Field(ge=0, le=1)
    unsupported_claims: list[str]
    reason: str


class JudgeError(Exception):
    """El modelo juez rechazó responder (`parsed is None`)."""


def judge_context(state: dict) -> str:
    """Contexto exacto que vio el modelo que respondió: fragmentos completos de `state["results"]` y, si hubo
    sección (`state["section"]`), su texto con el tope `SECTION_MAX_CHARS` en lugar del primer fragmento."""
    section = state.get("section")
    section_text = cap_section(section["content"]) if section else None
    return build_context(chunks_from_results(state["results"]), section_text)


def judge_answer(
    client, question: str, context: str, answer: str, model: str = JUDGE_MODEL
) -> tuple[Judgment, int, int]:
    """Devuelve `(juicio, prompt_tokens, completion_tokens)`."""
    resp = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nContext:\n\n{context}\n\nAnswer:\n{answer}",
            },
        ],
        response_format=Judgment,
        temperature=0,
    )
    message = resp.choices[0].message
    if message.parsed is None:
        raise JudgeError(message.refusal or "judge refused")
    return message.parsed, resp.usage.prompt_tokens, resp.usage.completion_tokens
