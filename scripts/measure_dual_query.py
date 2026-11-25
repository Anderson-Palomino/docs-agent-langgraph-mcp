"""Medición de la búsqueda doble (opción C, D40): una sola vez, sin meterla al agente.

Para cada caso en español que el clasificador tradujo, busca con la pregunta original y con su
traducción al inglés (`search_query`), y compara la mejor distancia de cada una. Lee el JSON de
resultados de `evaluate.py` (`{"run", "cases": [...]}`). El gasto en embeddings lo registra el
propio servidor MCP en el tipo `eval` (`MCP_BUDGET_SCOPE=eval`), igual que en `evaluate.py`.

    uv run python scripts/measure_dual_query.py eval/results/AAAA-MM-DD.json --out eval/dual_query.md
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BUDGET = 2


async def _search(tools, query: str, k: int) -> tuple[float | None, str]:
    """Mejor distancia y URL del primer resultado (`None` y "" si no hubo resultados)."""
    out = await tools.call("search_docs", {"query": query, "k": k, "include_content": False})
    results = out.get("results") or []
    dist = out.get("best_distance")
    if dist is None and results:
        dist = results[0].get("distance")
    return dist, (results[0].get("url", "") if results else "")


async def measure(cases: list[dict], tools, k: int = 5) -> list[dict]:
    """Dos búsquedas por caso `es` traducido: la pregunta original y la consulta en inglés."""
    rows = []
    for c in cases:
        if c.get("lang") != "es" or not c.get("translated"):
            continue
        d_orig, url_orig = await _search(tools, c["question"], k)
        d_trad, url_trad = await _search(tools, c["search_query"], k)
        # Distancia menor = más cercano; sin resultados cuenta como peor. Empate: gana la original.
        best = "translated" if d_trad is not None and (d_orig is None or d_trad < d_orig) else "original"
        rows.append({
            "id": c["id"],
            "expected_route": c.get("expected_route"),
            "distance_original": d_orig,
            "distance_translated": d_trad,
            "top_url_original": url_orig,
            "top_url_translated": url_trad,
            "best_from": best,
        })
    return rows


def _fmt(d: float | None) -> str:
    return "-" if d is None else f"{d:.3f}"


def render_dual(rows: list[dict]) -> str:
    """Tabla markdown (en español) para pegar en D40, con una fila por caso."""
    lines = [
        "| caso | ruta esperada | dist. original | dist. traducida | mejor | URL top original | URL top traducida |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        mejor = "traducida" if r["best_from"] == "translated" else "original"
        lines.append(
            f"| {r['id']} | {r['expected_route']} | {_fmt(r['distance_original'])} | "
            f"{_fmt(r['distance_translated'])} | {mejor} | {r['top_url_original']} | {r['top_url_translated']} |"
        )
    return "\n".join(lines) + "\n"


async def _run(cases: list[dict], settings) -> list[dict]:
    """Una sola tarea: la sesión MCP se abre y se cierra en la misma (ver `mcp_client`)."""
    from docs_agent.agent.mcp_client import DocsMCPClient, stdio_connect
    from docs_agent.budget import KIND_EVAL

    tools = DocsMCPClient(stdio_connect(settings, KIND_EVAL), settings.mcp_call_timeout_s)
    try:
        await tools.call("list_sources", {})  # arranque del servidor; no gasta tokens
        return await measure(cases, tools, settings.top_k)
    finally:
        await tools.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mide la búsqueda doble (original vs traducida).")
    parser.add_argument("results", type=Path, help="JSON de resultados de evaluate.py")
    parser.add_argument("--out", type=Path, required=True, help="archivo markdown de salida")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cases = json.loads(args.results.read_text(encoding="utf-8")).get("cases", [])

    import psycopg

    from docs_agent.agent.mcp_client import DocsServerUnavailable, DocsToolError
    from docs_agent.budget import KIND_EVAL, BudgetExceeded, check_budget, daily_limit
    from docs_agent.config import get_settings
    from docs_agent.db import connect

    settings = get_settings()
    try:
        with connect(settings.database_url) as conn:
            try:
                check_budget(conn, KIND_EVAL, daily_limit(settings, KIND_EVAL))
            except BudgetExceeded as exc:
                print(f"Presupuesto diario `eval` agotado: {exc}")
                return EXIT_BUDGET
            rows = asyncio.run(_run(cases, settings))
    except (DocsServerUnavailable, DocsToolError) as exc:
        print(f"No se pudo usar el servidor MCP ({type(exc).__name__}).")
        return EXIT_FAILED
    except psycopg.Error as exc:  # solo el tipo: libpq puede repetir parte de DATABASE_URL
        print(f"Error de base de datos ({type(exc).__name__}).")
        return EXIT_FAILED
    except Exception as exc:
        print(f"Error inesperado ({type(exc).__name__}).")
        return EXIT_FAILED

    args.out.write_text(render_dual(rows), encoding="utf-8")
    print(f"{len(rows)} casos medidos; escrito {args.out}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
