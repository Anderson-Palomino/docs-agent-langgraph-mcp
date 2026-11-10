"""Calibra el umbral de "no sé" (D21): mejor distancia coseno de 20 preguntas contra el corpus demo.

Uso: uv run python scripts/calibrate_threshold.py
Usa OPENAI_API_KEY y DATABASE_URL (db demo `docs`) desde Settings; cuenta los tokens en el presupuesto `ask`.
"""

import json
from pathlib import Path

from openai import OpenAI

from docs_agent.budget import KIND_ASK, check_budget, record_usage
from docs_agent.config import get_settings
from docs_agent.db import connect
from docs_agent.ingest.embed import embed_texts
from docs_agent.rag.retrieve import search

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = Path(__file__).with_name("calibration_questions.json")
OUTPUT = ROOT / "docs" / "calibracion-umbral.md"


def main() -> None:
    settings = get_settings()
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    items = [(q, g) for g in ("in_corpus", "out_of_corpus") for q in data[g]]
    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
    with connect(settings.database_url) as conn:
        check_budget(conn, KIND_ASK, settings.ask_daily_token_budget)
        vectors, tokens = embed_texts(client, [q for q, _ in items], settings.embedding_model)
        record_usage(conn, KIND_ASK, tokens)
        rows = []
        for (q, g), vec in zip(items, vectors):
            hits = search(conn, vec, settings.fastapi_docs_ref, k=1)
            rows.append((q, g, hits[0].distance, hits[0].url) if hits else (q, g, float("inf"), "-"))
    rows.sort(key=lambda r: r[2])

    lines = [
        "| Pregunta | Grupo | Mejor distancia | URL |",
        "|---|---|---|---|",
    ]
    for q, g, d, url in rows:
        lines.append(f"| {q} | {g} | {d:.4f} | {url} |")
    table = "\n".join(lines)
    print(table)
    print(f"\ntokens de embedding: {tokens}")

    header = (
        "# Calibración del umbral de \"no sé\"\n\n"
        f"Mejor distancia coseno (k=1) de 20 preguntas contra `{settings.fastapi_docs_ref}` "
        f"(modelo `{settings.embedding_model}`), ordenadas de menor a mayor. "
        "Generado por `scripts/calibrate_threshold.py` con `scripts/calibration_questions.json`.\n\n"
    )
    OUTPUT.write_text(header + table + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
