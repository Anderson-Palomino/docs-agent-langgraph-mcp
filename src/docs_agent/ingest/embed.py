"""Embeddings por lotes con el cliente de OpenAI."""


def embed_texts(
    client, texts: list[str], model: str, batch_size: int = 100
) -> tuple[list[list[float]], int]:
    """Vectores en el mismo orden que `texts` y tokens totales según `usage`."""
    vectors: list[list[float]] = []
    total_tokens = 0
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        vectors.extend(list(item.embedding) for item in resp.data)
        total_tokens += resp.usage.total_tokens
    return vectors, total_tokens
