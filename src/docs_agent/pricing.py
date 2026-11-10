"""Costo estimado en USD a partir del `usage` del grafo (precios por millón de tokens en `Settings`)."""

from docs_agent.config import Settings

PER_MTOK = 1_000_000


def _chat_tokens(usage: dict) -> tuple[int, int]:
    """(entrada, salida) de chat: clasificador + respuesta.

    El estado del grafo trae el clasificador desglosado (`classifier_prompt_tokens`/`classifier_completion_tokens`)
    y se cobra cada parte a su tarifa. La respuesta de `/ask` solo trae el total `classifier_tokens`
    (entrada + salida): ese total se cobra a la tarifa de ENTRADA, porque la salida del clasificador es un JSON
    mínimo; si el supuesto falla, la subestimación es una fracción de centavo.
    """
    tokens_in = usage.get("prompt_tokens", 0) + usage.get("classifier_prompt_tokens", 0)
    tokens_in += usage.get("classifier_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0) + usage.get("classifier_completion_tokens", 0)
    return tokens_in, tokens_out


def cost_usd(usage: dict, settings: Settings) -> float:
    tokens_in, tokens_out = _chat_tokens(usage)
    return (
        tokens_in * settings.price_chat_input_per_mtok
        + tokens_out * settings.price_chat_output_per_mtok
        + usage.get("embedding_tokens", 0) * settings.price_embedding_per_mtok
    ) / PER_MTOK


def total_tokens(usage: dict) -> int:
    tokens_in, tokens_out = _chat_tokens(usage)
    return tokens_in + tokens_out + usage.get("embedding_tokens", 0)
