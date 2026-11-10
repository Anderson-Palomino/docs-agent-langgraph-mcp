"""Ensayo de la demo de 2 minutos: corre los 3 momentos contra el servidor MCP real y cierra con una tabla.

Uso:
    uv run python scripts/demo_check.py                       # momentos 1-3 + pytest
    uv run python scripts/demo_check.py --q "pregunta" [--skip-tests]

Momento 1 llama `list_sources` directo por MCP (ruta `tool`); los momentos 2 y 3 (y `--q`) pasan por el grafo
con el mismo cableado que `/ask` (presupuesto `ask`, tracing LangSmith si está activo, corrida `ask`).
Códigos de salida: 0 todo ✓; 1 algún ✗, pytest falló o error del servidor/modelo; 2 presupuesto agotado.
La tabla se imprime después de cerrar la sesión MCP, para que el stderr del servidor (`[mcp] ...`) no se
mezcle con ella.
"""

import argparse
import asyncio
import os
import re
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import psycopg

from rich.console import Console
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parent.parent

MOMENTS = {
    1: "¿Qué documentación tienes disponible?",
    2: "¿Cómo protejo un endpoint con OAuth2 en FastAPI y obtengo el usuario actual? Muéstrame la sección exacta.",
    3: "¿Cómo configuro permisos en Django REST Framework?",
}
SECURITY_PATH = "/tutorial/security/"
CHECKLIST = "[ ] Claude no explica cómo configurar permisos de DRF; a lo sumo dice que la doc lo menciona como inspiración."
QUESTION_MAX_CHARS = 1000  # igual que la validación de `/ask`
PYTEST_TIMEOUT_S = 600
COLUMNS = ("Pregunta", "Ruta", "Herramientas", "Tokens", "Costo USD", "Latencia ms", "✓/✗")
EXIT_FAILED = 1
EXIT_BUDGET = 2


@dataclass
class Row:
    question: str
    route: str
    tools: list[str]
    tokens: int
    cost_usd: float
    latency_ms: float
    ok: bool | None  # None: sin esperado (`--q`), columna vacía


class DemoAbort(Exception):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


# --- lógica pura (tests/test_demo_check.py) ---


def _citation_url(citation) -> str:
    return citation["url"] if isinstance(citation, dict) else citation.url


def evaluate_expectation(moment: int, state: dict) -> bool:
    """¿El estado final cumple lo esperado del momento? (1: corpus listado; 2: respuesta con sección; 3: no_se)."""
    if moment == 1:
        sources = state.get("sources") or {}
        return state.get("route") == "tool" and sources.get("pages", 0) > 0 and sources.get("chunks", 0) > 0
    if moment == 2:
        return (
            state.get("route") == "answer"
            and "get_section" in state.get("tools_used", [])
            and any(SECURITY_PATH in _citation_url(c) for c in state.get("citations", []))
        )
    if moment == 3:
        return state.get("route") == "no_se" and state.get("reason") == "out_of_domain"
    raise ValueError(f"unknown moment: {moment}")


def parse_passed(pytest_output: str) -> int | None:
    """Tests que pasaron según la línea final de pytest (la última coincidencia: un traceback previo puede
    contener otro "N passed")."""
    matches = re.findall(r"(\d+) passed", pytest_output)
    return int(matches[-1]) if matches else None


async def invoke_recording(
    invoke: Callable[[], Awaitable[dict]], record: Callable[[], None], warn: Callable[[str], None]
) -> dict:
    """Corre el grafo y registra lo gastado siempre (como el `finally` de `/ask`).

    Si el grafo falló, un error al registrar no tapa el error original: se avisa en una línea y se relanza el
    original. Si el grafo terminó bien, el error de base de datos se propaga.
    """
    try:
        state = await invoke()
    except BaseException:
        try:
            await asyncio.to_thread(record)
        except psycopg.Error as exc:
            warn(f"no se pudo registrar el gasto de tokens: {type(exc).__name__}")
        raise
    await asyncio.to_thread(record)
    return state


def _mark(ok: bool | None) -> Text:
    if ok is None:
        return Text("")
    return Text("✓", style="bold green") if ok else Text("✗", style="bold red")


def _tests_line(summary: dict) -> str:
    if summary.get("tests_skipped"):
        return "tests: omitidos (--skip-tests)"
    passed = summary.get("tests_passed")
    line = f"{passed} tests passed" if passed is not None else "tests: no se pudo leer el resultado de pytest"
    if summary.get("tests_failed"):
        line += " · pytest falló"
    return line


def render(rows: list[Row], summary: dict) -> Table:
    """Tabla final de la demo; debajo (caption): costo total, latencia promedio y tests."""
    caption = "\n".join(
        [
            f"Costo total: {summary['total_cost_usd']:.5f} USD",
            f"Latencia promedio: {summary['avg_latency_ms']:,.0f} ms",
            _tests_line(summary),
        ]
    )
    table = Table(title="docs-agent · ensayo de la demo", caption=caption, caption_justify="left")
    table.add_column(COLUMNS[0], max_width=46)
    table.add_column(COLUMNS[1], no_wrap=True)
    table.add_column(COLUMNS[2])
    table.add_column(COLUMNS[3], justify="right")
    table.add_column(COLUMNS[4], justify="right")
    table.add_column(COLUMNS[5], justify="right")
    table.add_column(COLUMNS[6], justify="center")
    for r in rows:
        table.add_row(
            r.question,
            r.route,
            ", ".join(r.tools) or "—",
            f"{r.tokens:,}",
            f"{r.cost_usd:.5f}",
            f"{r.latency_ms:,.0f}",
            _mark(r.ok),
        )
    return table


# --- ejecución real (OpenAI + servidor MCP por stdio) ---


def _route_label(state: dict) -> str:
    reason = state.get("reason")
    return f"{state['route']} · {reason}" if reason else state["route"]


async def _run(questions: list[tuple[int | None, str]], settings, conn, client, console: Console) -> list[Row]:
    """Todo en una sola tarea: la sesión MCP se abre y se cierra en la misma (ver `mcp_client`)."""
    import openai

    from docs_agent.agent.graph import build_graph, is_budget_error
    from docs_agent.agent.mcp_client import DocsMCPClient, DocsServerUnavailable, DocsToolError, stdio_connect
    from docs_agent.agent.runner import invoke_config, make_deps, record_spent
    from docs_agent.budget import BudgetExceeded
    from docs_agent.pricing import cost_usd, total_tokens

    tools = DocsMCPClient(stdio_connect(settings, "ask"), settings.mcp_call_timeout_s)
    rows: list[Row] = []
    try:
        # Arranque del servidor fuera del cronómetro: la sesión es perezosa y el primer `call` lanza el proceso
        # (~4 s en Windows), que de otro modo se cargaría a la latencia del primer momento. No gasta tokens.
        console.print("[dim]arrancando servidor MCP ...[/]")
        await tools.call("list_sources", {})
        for i, (moment, question) in enumerate(questions, 1):
            console.print(f"[dim]{i}/{len(questions)} {question}[/]")
            start = time.perf_counter()
            if moment == 1:
                sources = await tools.call("list_sources", {})
                latency = (time.perf_counter() - start) * 1000
                state = {"route": "tool", "tools_used": ["list_sources"], "sources": sources}
                rows.append(Row(question, "tool", ["list_sources"], 0, 0.0, latency, evaluate_expectation(1, state)))
                continue
            deps = make_deps(conn, client, tools, settings)
            state = await invoke_recording(
                lambda: build_graph(deps).ainvoke(
                    {"question": question}, config=invoke_config(question, source="demo_check")
                ),
                lambda: record_spent(conn, deps),
                lambda msg: console.print(f"[yellow]aviso: {msg}[/]"),
            )
            latency = (time.perf_counter() - start) * 1000
            usage = state["usage"]
            ok = evaluate_expectation(moment, state) if moment is not None else None
            rows.append(
                Row(
                    question,
                    _route_label(state),
                    state.get("tools_used", []),
                    total_tokens(usage),
                    cost_usd(usage, settings),
                    latency,
                    ok,
                )
            )
    except BudgetExceeded as exc:
        raise DemoAbort(f"Presupuesto diario `ask` agotado: {exc}", EXIT_BUDGET) from exc
    except DocsToolError as exc:
        if is_budget_error(exc):
            raise DemoAbort("Presupuesto diario `ask` agotado (lo cortó el servidor MCP).", EXIT_BUDGET) from exc
        raise DemoAbort(f"Error de herramienta MCP: {exc}", EXIT_FAILED) from exc
    except DocsServerUnavailable as exc:
        raise DemoAbort(f"Servidor MCP no disponible: {exc}", EXIT_FAILED) from exc
    except openai.OpenAIError as exc:
        raise DemoAbort(f"Error del modelo (OpenAI): {type(exc).__name__}", EXIT_FAILED) from exc
    finally:
        await tools.aclose()
    return rows


def _run_pytest(env: dict[str, str]) -> tuple[int | None, bool]:
    """(tests que pasaron, falló) con el entorno previo al tracing: ningún test debe hablar con LangSmith."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PYTEST_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print(f"pytest superó {PYTEST_TIMEOUT_S} s y se cortó.", file=sys.stderr)
        return None, True
    return parse_passed(proc.stdout), proc.returncode != 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ensayo de la demo: 3 momentos + tabla final.")
    parser.add_argument("--q", help="corre solo esta pregunta por el grafo (sin esperado)")
    parser.add_argument("--skip-tests", action="store_true", help="no correr pytest")
    args = parser.parse_args(argv)
    question = None
    if args.q is not None:
        question = args.q.strip()
        if not 1 <= len(question) <= QUESTION_MAX_CHARS:
            parser.error(f"--q debe tener entre 1 y {QUESTION_MAX_CHARS} caracteres")

    # La consola de Windows (o una tubería en cp1252) no siempre es UTF-8: ✓/✗ y los acentos deben salir bien.
    if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    console = Console(width=None if sys.stdout.isatty() else 140)

    from docs_agent.api import make_openai
    from docs_agent.budget import KIND_ASK, BudgetExceeded, check_budget
    from docs_agent.config import get_settings
    from docs_agent.db import connect
    from docs_agent.rag.retrieve import corpus_size
    from docs_agent.tracing import configure_tracing, load_openai_wrapper

    settings = get_settings()
    if not settings.openai_api_key.get_secret_value():
        console.print("[red]OPENAI_API_KEY no configurada.[/]")
        return EXIT_FAILED

    env_before_tracing = dict(os.environ)
    # Igual que el lifespan de la API (D34): antes de lanzar el servidor stdio, que hereda `os.environ`.
    tracing = configure_tracing(settings)
    wrapper = load_openai_wrapper() if tracing else None
    console.print(f"[dim]tracing LangSmith: {'activo · proyecto ' + settings.langsmith_project if tracing else 'apagado'}[/]")

    if question is not None:
        questions: list[tuple[int | None, str]] = [(None, question)]
    else:
        questions = list(MOMENTS.items())

    try:
        with connect(settings.database_url) as conn:
            try:
                check_budget(conn, KIND_ASK, settings.ask_daily_token_budget)
            except BudgetExceeded as exc:
                console.print(f"[red]Presupuesto diario `ask` agotado: {exc}[/]")
                return EXIT_BUDGET
            if corpus_size(conn, settings.fastapi_docs_ref) == 0:
                console.print("[red]El corpus está vacío: corre primero la ingesta.[/]")
                return EXIT_FAILED
            try:
                rows = asyncio.run(_run(questions, settings, conn, make_openai(wrapper), console))
            except DemoAbort as exc:
                console.print(f"[red]{exc}[/]")
                return exc.exit_code
    except psycopg.Error as exc:
        # Solo el tipo: el mensaje de libpq puede repetir parte de DATABASE_URL (p. ej. si está mal formada).
        console.print(Text(f"Error de base de datos ({type(exc).__name__}). Revisa que Postgres esté arriba y DATABASE_URL.", style="red"))
        return EXIT_FAILED

    summary = {
        "total_cost_usd": sum(r.cost_usd for r in rows),
        "avg_latency_ms": sum(r.latency_ms for r in rows) / len(rows),
        "tests_passed": None,
        "tests_failed": False,
        "tests_skipped": args.skip_tests,
    }
    if not args.skip_tests:
        console.print("[dim]corriendo pytest -q ...[/]")
        summary["tests_passed"], summary["tests_failed"] = _run_pytest(env_before_tracing)

    console.print()
    console.print(render(rows, summary))
    console.print()
    console.print(CHECKLIST, markup=False)
    failed = any(r.ok is False for r in rows) or summary["tests_failed"]
    return EXIT_FAILED if failed else 0


if __name__ == "__main__":
    sys.exit(main())
