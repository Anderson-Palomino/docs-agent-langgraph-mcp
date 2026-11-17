"""Calibra el umbral de "no sé" (D21): mejor distancia coseno de 20 preguntas contra el corpus demo.

Uso: uv run python scripts/calibrate_threshold.py
Usa OPENAI_API_KEY y DATABASE_URL (db demo `docs`) desde Settings; cuenta los tokens en el presupuesto `ask`.

Modo offline: uv run python scripts/calibrate_threshold.py --from-results eval/results/<fecha>.json [--output RUTA]
Lee una corrida de scripts/evaluate.py y escribe la calibración (casos por distancia + simulación de umbrales)
sin llamar a OpenAI ni a la base de datos.
"""

import argparse
import json
from pathlib import Path

from openai import OpenAI

from docs_agent.budget import KIND_ASK, check_budget, record_usage
from docs_agent.config import get_settings
from docs_agent.db import connect
from docs_agent.evaluation.metrics import threshold_sweep
from docs_agent.evaluation.report import sweep_table
from docs_agent.ingest.embed import embed_texts
from docs_agent.rag.retrieve import search

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = Path(__file__).with_name("calibration_questions.json")
OUTPUT = ROOT / "docs" / "calibracion-umbral.md"


def _url(case: dict) -> str:
    urls = case.get("retrieved_urls") or []
    return urls[0] if urls else "-"


def from_results(results_path: Path, output: Path) -> str:
    """Escribe la calibración a partir de una corrida de evaluate.py (sin OpenAI). Devuelve el markdown."""
    data = json.loads(Path(results_path).read_text(encoding="utf-8"))
    run, cases = data["run"], data["cases"]
    ok = [c for c in cases if not c.get("error")]
    failed = [c for c in cases if c.get("error")]
    ranked = sorted(ok, key=lambda c: float("inf") if c["best_distance"] is None else c["best_distance"])

    lines = [
        "# Calibración del umbral de \"no sé\"",
        "",
        f"Generado por `scripts/calibrate_threshold.py --from-results` a partir de la corrida "
        f"`{Path(results_path).name}` del {run['date']} (umbral {run['threshold']:.2f} · k={run['top_k']} · "
        f"docs FastAPI {run['docs_ref']} · modelo `{run['chat_model']}`).",
        "",
        "Nota: la simulación mide solo la ruta (responde / \"no sé\"), no la fidelidad (faithfulness). "
        "Los casos `either` nunca cuentan como error bajo simulación (spec 5.1): no se conocen las citas.",
        "",
        "## Casos por mejor distancia",
        "",
        "| id | Pregunta | Esperada | Clasificador | Mejor distancia | URL |",
        "|---|---|---|---|---|---|",
    ]
    for c in ranked:
        cls = "rechazó" if c.get("reason") == "out_of_domain" else "aceptó"
        d = "-" if c["best_distance"] is None else f"{c['best_distance']:.4f}"
        lines.append(f"| {c['id']} | {c['question']} | {c['expected_route']} | {cls} | {d} | {_url(c)} |")
    if failed:
        lines += ["", "Excluidos por error: " + ", ".join(f"{c['id']} ({c['error']})" for c in failed) + "."]
    lines += ["", "## Umbrales (simulación offline sobre `best_distance`)", ""]
    lines += sweep_table(threshold_sweep(cases), run["threshold"])
    text = "\n".join(lines) + "\n"
    Path(output).write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-results", type=Path, help="JSON de una corrida de evaluate.py (modo offline)")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="archivo markdown de salida")
    args = parser.parse_args()
    if args.from_results:
        print(from_results(args.from_results, args.output))
        return
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
    args.output.write_text(header + table + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
