"""Tabla de revisión del golden set para el dueño: valida el set, comprueba las URLs contra `sections` y escribe el Markdown.

Uso:
    uv run python scripts/golden_review.py [--golden eval/golden_set.json] [--out eval/golden_set_review.md]

Solo lee la base local `docs` (tabla `sections`); no llama a OpenAI.
Una `expected_url` con `#ancla` existe si hay una sección con esa URL exacta; sin ancla, si hay alguna sección de
esa página (misma regla de coincidencia que la evaluación, spec 5.2).
Códigos de salida: 0 todo ✓ y distribución completa; 1 golden set inválido, URL inexistente, distribución
incompleta o error de base.
"""

import argparse
import sys
from pathlib import Path

import psycopg
from pydantic import ValidationError

from docs_agent.config import get_settings
from docs_agent.db import connect
from docs_agent.evaluation.golden import GoldenCase, GoldenSetError, check_distribution, load_golden

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_GOLDEN = ROOT / "eval" / "golden_set.json"
DEFAULT_OUT = ROOT / "eval" / "golden_set_review.md"
COLUMNS = (
    "id", "categoría", "lang", "pregunta", "ruta esperada", "URLs esperadas", "¿existe?", "notas", "comentario del dueño",
)
EXIT_FAILED = 1


def url_exists(url: str, known_urls: set[str]) -> bool:
    """¿La URL esperada apunta a algo indexado? Con ancla: exacta; sin ancla: cualquier sección de la página."""
    if "#" in url:
        return url in known_urls
    return any(k == url or k.startswith(url + "#") for k in known_urls)


def _cell(text: str) -> str:
    """Texto seguro para una celda de tabla Markdown (sin `|` ni saltos de línea)."""
    return text.replace("|", "\\|").replace("\n", " ")


def _display_path(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def render_review(
    cases: list[GoldenCase], known_urls: set[str], problems: list[str], source: Path = DEFAULT_GOLDEN, holdout: bool = False
) -> str:
    """Markdown de la tabla de revisión; la última columna queda vacía para el dueño.

    El encabezado nombra el archivo real (`source`); con `holdout` no se chequea la distribución y lo dice."""
    title = "Holdout en español: tabla de revisión" if holdout else "Golden set: tabla de revisión"
    distribution = "no aplica (holdout)" if holdout else ("completa" if not problems else "; ".join(problems))
    lines = [
        f"# {title}",
        "",
        f"Generado por `scripts/golden_review.py` desde `{_display_path(source)}`; no editar a mano.",
        "Escribe tus comentarios en la última columna (o aparte, citando el id).",
        "",
        f"Casos: {len(cases)}. Distribución: {distribution}.",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    for c in cases:
        urls = "<br>".join(c.expected_urls) or "—"
        marks = " ".join("✓" if url_exists(u, known_urls) else "✗" for u in c.expected_urls) or "—"
        question = _cell(c.question) + (" *(juez)*" if c.judge_review else "")
        lines.append(
            f"| {c.id} | {c.category} | {c.lang} | {question} | {c.expected_route} | {urls} | {marks} | "
            f"{_cell(c.notes)} |  |"
        )
    return "\n".join(lines) + "\n"


def _known_urls() -> set[str]:
    with connect(get_settings().database_url) as conn:
        return {row[0] for row in conn.execute("SELECT url FROM sections").fetchall()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--holdout", action="store_true", help="set de holdout: sin chequeo de distribución")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # ✓/✗ en consolas Windows que no son UTF-8
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() != "utf-8":
            stream.reconfigure(encoding="utf-8", errors="replace")

    try:
        cases = load_golden(args.golden)
    except GoldenSetError as exc:
        print(f"golden set inválido: {exc}", file=sys.stderr)
        return EXIT_FAILED
    try:
        known = _known_urls()
    except ValidationError as exc:  # Settings inválido: solo el tipo, nunca valores del entorno
        print(f"configuración inválida: {type(exc).__name__}", file=sys.stderr)
        return EXIT_FAILED
    except psycopg.Error as exc:
        print(f"no se pudo leer sections de la base local: {type(exc).__name__}", file=sys.stderr)
        return EXIT_FAILED

    problems = [] if args.holdout else check_distribution(cases)
    missing = [(c.id, u) for c in cases for u in c.expected_urls if not url_exists(u, known)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_review(cases, known, problems, args.golden, args.holdout), encoding="utf-8")

    for case_id, url in missing:
        print(f"✗ {case_id}: {url} no está en sections", file=sys.stderr)
    for problem in problems:
        print(f"✗ distribución: {problem}", file=sys.stderr)
    n_urls = sum(len(c.expected_urls) for c in cases)
    print(f"{len(cases)} casos, {n_urls - len(missing)}/{n_urls} URLs ✓ -> {args.out}")
    return EXIT_FAILED if missing or problems else 0


if __name__ == "__main__":
    sys.exit(main())
