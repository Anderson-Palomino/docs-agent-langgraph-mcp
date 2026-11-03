"""Dobles de prueba compartidos: ningún test llama a la API real de OpenAI."""

import hashlib
import math
import random
from types import SimpleNamespace

EMBEDDING_DIM = 1536


class FakeOpenAI:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.embeddings = SimpleNamespace(create=self._create_embeddings)

    @staticmethod
    def vector_for(text: str) -> list[float]:
        """Vector determinista de 1536 floats, normalizado, derivado del hash del texto."""
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        raw = [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]
        norm = math.sqrt(sum(x * x for x in raw))
        return [x / norm for x in raw]

    def _create_embeddings(self, model: str, input: list[str]):
        self.calls.append({"model": model, "input": list(input)})
        data = [SimpleNamespace(embedding=self.vector_for(t)) for t in input]
        tokens = sum(len(t.split()) or 1 for t in input)
        return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=tokens))
