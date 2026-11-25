"""Hoja de revisión del juez (D38): el dueño marca sí/no por afirmación y este script calcula la coincidencia.

Uso:
    uv run python scripts/judge_review_sheet.py eval/results/2026-11-24.json --out eval/results/2026-11-24-judge-review.md --extra g03,g06,g07,g09
    uv run python scripts/judge_review_sheet.py --score eval/results/2026-11-24-judge-review.md

Armar la hoja: los casos `judge_review` del golden set (`eval/golden_set.json`) más los `--extra` que la corrida
respondió (un extra con "no sé" no entra). Si pasan de 10, no escribe nada y avisa: hay que consultarlo con el dueño.
`--score` lee la hoja llena y muestra la coincidencia por afirmación y por caso. No llama a OpenAI ni a la base.
Códigos de salida: 0 ok; 1 entrada inválida o más de 10 casos.
"""

import argparse
import json
import sys
from pathlib import Path

from docs_agent.evaluation.golden import GoldenSetError, load_golden
from docs_agent.evaluation.report import (
    MAX_REVIEW_CASES,
    parse_review,
    render_judge_review,
    review_case_ids,
    score_review,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "eval" / "golden_set.json"
EXIT_FAILED = 1


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:.1f}%" if den else "—"


def print_score(path: Path) -> int:
    try:
        rows = parse_review(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"No se pudo leer la hoja: {exc}")
        return EXIT_FAILED
    s = score_review(rows)
    print(f"Afirmaciones respondidas: {s['claims_answered']} de {s['claims_total']}")
    print(f"Coincidencia por afirmación: {s['claims_agree']}/{s['claims_answered']} = {_pct(s['claims_agree'], s['claims_answered'])}")
    print(f"Casos respondidos completos: {s['cases_answered']} de {s['cases_total']}")
    print(f"Coincidencia por caso: {s['case_agree']}/{s['cases_answered']} = {_pct(s['case_agree'], s['cases_answered'])}")
    if s["claims_answered"] < s["claims_total"]:
        print("Aviso: la hoja no está completa; los números son parciales.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hoja de revisión del juez y cálculo de coincidencia.")
    parser.add_argument("results", nargs="?", type=Path, help="JSON de la corrida (eval/results/<día>.json)")
    parser.add_argument("--out", type=Path, help="dónde escribir la hoja")
    parser.add_argument("--extra", default="", help="ids extra separados por coma (se incluyen solo si respondieron)")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN, help="golden set con las marcas judge_review")
    parser.add_argument("--score", type=Path, help="hoja llena: imprime la coincidencia en lugar de armar una")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.score:
        return print_score(args.score)
    if not args.results or not args.out:
        parser.error("indica RESULTS.json y --out (o --score HOJA.md)")

    try:
        golden = load_golden(args.golden)
        cases = json.loads(args.results.read_text(encoding="utf-8"))["cases"]
    except (GoldenSetError, OSError, ValueError, KeyError) as exc:
        print(f"Entrada inválida: {exc}")
        return EXIT_FAILED
    extra = [s.strip() for s in args.extra.split(",") if s.strip()]
    unknown = [i for i in extra if i not in {g.id for g in golden}]
    if unknown:
        print(f"--extra: ids que no están en el golden set: {', '.join(unknown)}")
        return EXIT_FAILED
    ids = review_case_ids(cases, golden, extra)
    if len(ids) > MAX_REVIEW_CASES:
        print(
            f"La hoja tendría {len(ids)} casos ({', '.join(ids)}), más de {MAX_REVIEW_CASES}: "
            "avisa al dueño antes de armarla. No se escribió nada."
        )
        return EXIT_FAILED
    args.out.write_text(render_judge_review(cases, golden, extra), encoding="utf-8")
    print(f"Hoja con {len(ids)} casos: {', '.join(ids)} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
