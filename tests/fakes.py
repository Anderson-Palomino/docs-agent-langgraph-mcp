"""Dobles de prueba compartidos: ningún test llama a la API real de OpenAI."""

import hashlib
import math
import random
import re
from types import SimpleNamespace

import httpx
import openai

EMBEDDING_DIM = 1536


class FakeOpenAI:
    def __init__(self, parsed=None, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.parsed = parsed
        self.fail = fail
        self.embeddings = SimpleNamespace(create=self._create_embeddings)
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse_chat))

    @staticmethod
    def vector_for(text: str) -> list[float]:
        """Vector determinista de 1536 floats, normalizado, derivado del hash del texto."""
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        raw = [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]
        norm = math.sqrt(sum(x * x for x in raw))
        return [x / norm for x in raw]

    def _raise_if_failing(self) -> None:
        if self.fail:
            request = httpx.Request("POST", "https://api.openai.com/v1/x")
            raise openai.APIError("boom", request=request, body=None)

    def _create_embeddings(self, model: str, input: list[str]):
        self._raise_if_failing()
        self.calls.append({"model": model, "input": list(input)})
        data = [SimpleNamespace(embedding=self.vector_for(t)) for t in input]
        tokens = sum(len(t.split()) or 1 for t in input)
        return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=tokens))

    def _parse_chat(self, model, messages, response_format, temperature=None):
        self._raise_if_failing()
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        parsed = self.parsed
        if parsed is None:  # por defecto cita la primera URL que aparezca en los mensajes
            text = " ".join(m["content"] for m in messages)
            match = re.search(r"URL: (\S+)", text)
            parsed = response_format(answer="fake answer", citations=[match.group(1)] if match else [])
        message = SimpleNamespace(parsed=parsed, refusal=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )
