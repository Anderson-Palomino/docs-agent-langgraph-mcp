"""Compara dos corridas de `evaluate.py` (antes/después) en un markdown, con el holdout aparte (spec 5.2).

Uso:
    uv run python scripts/compare_runs.py eval/results/2026-11-17.json eval/results/2026-11-24.json \\
        --holdout eval/results/2026-11-24-holdout.json

Sin red ni base: solo lee los JSON. Por defecto escribe `eval/results/<día de DESPUÉS>-comparison.md`
(se puede regenerar, así que lo sobrescribe).
"""

import argparse
import json
import sys
from pathlib import Path

from docs_agent.evaluation.compare import render_comparison

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "eval" / "results"


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("before", type=Path, help="JSON de la corrida «antes»")
    parser.add_argument("after", type=Path, help="JSON de la corrida «después»")
    parser.add_argument("--holdout", type=Path, help="JSON de la corrida del holdout (tabla aparte)")
    parser.add_argument("--out", type=Path, help="markdown de salida (por defecto eval/results/<día>-comparison.md)")
    args = parser.parse_args(argv)

    before, after = _load(args.before), _load(args.after)
    holdout = _load(args.holdout) if args.holdout else None
    out = args.out or RESULTS_DIR / f"{after['run']['date']}-comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_comparison(before, after, holdout), encoding="utf-8")
    print(f"Comparación escrita en {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
