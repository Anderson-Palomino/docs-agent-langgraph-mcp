"""Conteo de tokens con la codificación de `text-embedding-3-small`."""

from functools import cache

import tiktoken


@cache
def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def encode(text: str) -> list[int]:
    return _encoder().encode(text)


def decode(tokens: list[int]) -> str:
    return _encoder().decode(tokens)


def count_tokens(text: str) -> int:
    return len(encode(text))
