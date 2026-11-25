"""Evaluación del grafo con el golden set (spec 5.2): corre cada caso como `/ask` y deja métricas y reportes.

Uso:
    uv run python scripts/evaluate.py                         # los 30 casos, con juez
    uv run python scripts/evaluate.py --only g01,g05 --no-judge
    uv run python scripts/evaluate.py --golden eval/holdout_es.json --holdout   # salidas `<día>-holdout.*`

Cada caso pasa por el mismo camino que `/ask` (`make_deps` + `build_graph(deps).ainvoke` dentro de
`invoke_recording`), con el servidor MCP real por stdio, pero todo el gasto va al kind `eval` (D39): grafo,
juez y servidor MCP (scope `eval`). `--max-tokens` es un tope por corrida, aparte del presupuesto diario.
Salidas en `eval/results/<día Lima>.json`, `.md` y `-judge-review.md` (sin pisar corridas anteriores).
Códigos de salida (como `scripts/demo_check.py`): 0 ok; 1 golden set inválido, algún caso con error o fallo
del servidor/modelo/base; 2 presupuesto (`--max-tokens` o el diario `eval`).
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

from rich.console import Console
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "eval" / "golden_set.json"
RESULTS_DIR = ROOT / "eval" / "results"
DEFAULT_MAX_TOKENS = 400_000
LIMA = ZoneInfo("America/Lima")  # el día del archivo es el de quien corre la evaluación (spec 5.2)
EXIT_FAILED = 1
EXIT_BUDGET = 2
ABORT_MAX_TOKENS = "max_tokens"
ABORT_BUDGET = "budget"
ABORT_CRASH = "crash"  # `crash:<Tipo>`: error inesperado a mitad de corrida, con resultados parciales


class _BudgetAbort(Exception):
    """Interno: el presupuesto diario `eval` se agotó; la corrida para."""


# --- un caso ---


def _new_row(case) -> dict:
    """Caso resultado con todas las claves que leen `metrics` y `report` (también si termina en error)."""
    return {
        "id": case.id,
        "question": case.question,
        "lang": case.lang,
        "category": case.category,
        "expected_route": case.expected_route,
        "expected_urls": list(case.expected_urls),
        "route": None,
        "reason": None,
        "is_fastapi": None,
        "classifier_reason": None,
        "language": None,  # idioma que detectó el clasificador ("es" | "en")
        "search_query": None,  # consulta que el grafo realmente usó para buscar
        "translated": None,  # True si la consulta de búsqueda es una traducción de la pregunta
        "best_distance": None,
        "retrieved_urls": [],
        "citations": [],
        "grounded": None,
        "answer": None,
        "tools_used": [],
        "usage": None,
        "tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": None,
        "judge_context": None,
        "context_parts": [],
        "judge": None,
        "judge_tokens": 0,
        "judge_cost_usd": 0.0,
        "judge_error": None,
        "error": None,
    }


def _context_parts(state: dict) -> list[dict]:
    """Cabeceras de los fragmentos del contexto (`build_context`): con sección, el [1] lleva su texto completo."""
    has_section = state.get("section") is not None
    return [
        {"n": i, "title": r["title"], "url": r["url"], "section": has_section and i == 1}
        for i, r in enumerate(state.get("results") or [], start=1)
    ]


def _fill_from_state(row: dict, state: dict, judge_context) -> None:
    row.update(
        route=state["route"],
        reason=state.get("reason"),
        is_fastapi=state.get("reason") != "out_of_domain",  # solo el clasificador pone `out_of_domain`
        classifier_reason=state.get("classifier_reason"),
        language=state.get("language"),
        search_query=state.get("search_query"),
        translated=state.get("translated"),
        best_distance=state.get("best_distance"),
        retrieved_urls=[r["url"] for r in state.get("results") or []],
        citations=[c["url"] if isinstance(c, dict) else c.url for c in state.get("citations", [])],
        grounded=state.get("grounded"),
        answer=state.get("answer"),
        tools_used=list(state.get("tools_used", [])),
        usage=dict(state["usage"]),
    )
    if state["route"] == "answer":
        row["judge_context"] = judge_context(state)
        row["context_parts"] = _context_parts(state)


def _settle_cost(row: dict, deps, settings) -> None:
    """Tokens y costo del caso (sin el juez). Si el grafo falló no hay `usage`: se cuentan los tokens de chat que
    ya volvieron (`deps.spent`), cobrados a la tarifa de entrada; los embeddings de esa búsqueda no se conocen."""
    from docs_agent.pricing import cost_usd, total_tokens

    usage = row["usage"] if row["usage"] is not None else {"prompt_tokens": deps.spent["chat_tokens"]}
    row["tokens"] = total_tokens(usage)
    row["cost_usd"] = cost_usd(usage, settings)


async def run_cases(
    cases, settings, conn, client, tools, judge: bool, max_tokens: int, console, results: list[dict] | None = None
) -> tuple[list[dict], str | None]:
    """Corre los casos en orden; devuelve `(resultados, aborted)` con `aborted` = None | "max_tokens" | "budget".

    Un error de herramienta, del servidor MCP o de OpenAI queda en `error` del caso y la corrida sigue; el juez
    que falla deja `judge_error` y el caso conserva el resultado del grafo. Los resultados se van agregando a
    `results` (si se pasa): ante un error inesperado que escapa, quien llama conserva los parciales.
    """
    import openai
    from pydantic import ValidationError

    from docs_agent.agent.graph import build_graph, is_budget_error
    from docs_agent.agent.mcp_client import DocsServerUnavailable, DocsToolError
    from docs_agent.agent.runner import invoke_config, invoke_recording, make_deps, record_spent
    from docs_agent.budget import KIND_EVAL, BudgetExceeded, check_budget, daily_limit, record_usage
    from docs_agent.evaluation.judge import JudgeError, judge_answer, judge_context
    from docs_agent.pricing import cost_usd

    results = results if results is not None else []
    spent = 0  # tokens de la corrida: grafo + búsquedas extra + juez
    for i, case in enumerate(cases, 1):
        if spent >= max_tokens:
            console.print(Text(f"Tope --max-tokens alcanzado ({spent:,} ≥ {max_tokens:,}): se para.", style="yellow"))
            return results, ABORT_MAX_TOKENS
        console.print(Text(f"{i}/{len(cases)} {case.id} {case.question}", style="dim"))
        row = _new_row(case)
        results.append(row)
        deps = make_deps(conn, client, tools, settings, kind=KIND_EVAL)
        graph = build_graph(deps)  # compilar fuera del cronómetro: la latencia es solo el `ainvoke`
        timing: dict[str, float] = {}

        def charge_judge(pt: int, ct: int) -> None:
            row["judge_tokens"] = pt + ct
            # El juez es el mismo modelo que responde (D38): se cobra con las tarifas de chat (`main` avisa si no).
            row["judge_cost_usd"] = cost_usd({"prompt_tokens": pt, "completion_tokens": ct}, settings)

        async def invoke(q=case.question, cid=case.id, graph=graph):
            start = time.perf_counter()
            try:
                return await graph.ainvoke(
                    {"question": q}, config=invoke_config(q, source="evaluate", case_id=cid)
                )
            finally:
                timing["ms"] = (time.perf_counter() - start) * 1000

        aborted = None
        try:
            state = await invoke_recording(
                invoke,
                lambda: record_spent(conn, deps, kind=KIND_EVAL),
                lambda msg: console.print(Text(f"aviso: {msg}", style="yellow")),
            )
            row["latency_ms"] = timing["ms"]
            _fill_from_state(row, state, judge_context)
            if state["reason"] == "out_of_domain":
                # No buscó: búsqueda aparte solo para `best_distance` y URLs; no cambia la ruta registrada.
                extra = await tools.call("search_docs", {"query": state.get("search_query") or case.question, "k": settings.top_k})
                row["best_distance"] = extra["best_distance"]
                row["retrieved_urls"] = list(dict.fromkeys(r["url"] for r in extra["results"]))
                row["usage"]["embedding_tokens"] = row["usage"].get("embedding_tokens", 0) + extra.get(
                    "embedding_tokens", 0
                )
            if judge and row["route"] == "answer":
                try:
                    await asyncio.to_thread(check_budget, conn, KIND_EVAL, daily_limit(settings, KIND_EVAL))
                except BudgetExceeded as exc:
                    row["judge_error"] = type(exc).__name__
                    raise _BudgetAbort() from exc
                try:
                    judgment, pt, ct = await asyncio.to_thread(
                        judge_answer, client, case.question, row["judge_context"], row["answer"]
                    )
                except JudgeError as exc:  # rechazo: los tokens igual se gastaron
                    row["judge_error"] = type(exc).__name__
                    charge_judge(exc.prompt_tokens, exc.completion_tokens)
                    if row["judge_tokens"]:
                        await asyncio.to_thread(record_usage, conn, KIND_EVAL, row["judge_tokens"])
                except (ValidationError, openai.OpenAIError) as exc:  # sin `usage` que contar
                    row["judge_error"] = type(exc).__name__
                else:
                    await asyncio.to_thread(record_usage, conn, KIND_EVAL, pt + ct)
                    row["judge"] = judgment.model_dump()
                    charge_judge(pt, ct)
        except _BudgetAbort:
            aborted = ABORT_BUDGET
        except BudgetExceeded as exc:
            row["error"] = type(exc).__name__
            aborted = ABORT_BUDGET
        except DocsToolError as exc:
            row["error"] = type(exc).__name__
            if is_budget_error(exc):  # lo cortó el presupuesto `eval` del servidor MCP
                aborted = ABORT_BUDGET
        except (DocsServerUnavailable, openai.OpenAIError) as exc:
            row["error"] = type(exc).__name__
        except BaseException as exc:  # inesperado: queda marcado en el caso y sube (`main` guarda los parciales)
            row["error"] = type(exc).__name__
            raise
        finally:
            if row["latency_ms"] is None and "ms" in timing:  # el grafo falló: igual se cronometró
                row["latency_ms"] = timing["ms"]
            _settle_cost(row, deps, settings)
            spent += row["tokens"] + row["judge_tokens"]
        if row["error"]:
            console.print(Text(f"  {case.id}: error {row['error']}", style="yellow"))
        elif row["judge_error"]:
            console.print(Text(f"  {case.id}: juez sin juicio ({row['judge_error']})", style="yellow"))
        if aborted:
            console.print(Text("Presupuesto diario `eval` agotado: se para.", style="red"))
            return results, aborted
    return results, None


# --- golden set, salidas y código de salida ---


def select_cases(path: Path, only: str | None, holdout: bool = False) -> list:
    """Golden set validado; con `--only`, solo esos ids (deben existir) y sin chequeo de distribución.

    `holdout=True` (set aparte, p. ej. `eval/holdout_es.json`): valida cada caso pero no exige la distribución de 30."""
    from docs_agent.evaluation.golden import GoldenSetError, check_distribution, load_golden

    cases = load_golden(path)
    if only is not None:
        ids = [s.strip() for s in only.split(",") if s.strip()]
        known = {c.id for c in cases}
        unknown = [i for i in ids if i not in known]
        if not ids or unknown:
            raise GoldenSetError(f"--only: ids desconocidos: {', '.join(unknown) or '(vacío)'}")
        wanted = set(ids)
        return [c for c in cases if c.id in wanted]
    problems = [] if holdout else check_distribution(cases)
    if problems:
        raise GoldenSetError("el golden set no cumple la distribución: " + "; ".join(problems))
    return cases


def _display_path(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def build_run_info(settings, day: date, golden_path: Path, only, max_tokens: int, judge: bool, aborted, results) -> dict:
    """Config de la corrida y gasto de **todos** los casos, incluidos los que terminaron en error."""
    from docs_agent.evaluation.judge import JUDGE_MODEL

    return {
        "date": day.isoformat(),
        "chat_model": settings.chat_model,
        "judge_model": JUDGE_MODEL,
        "judge": judge,
        "threshold": settings.no_answer_distance_threshold,
        "top_k": settings.top_k,
        "docs_ref": settings.fastapi_docs_ref,
        "golden": _display_path(golden_path),
        "only": [s.strip() for s in only.split(",") if s.strip()] if only else None,
        "max_tokens": max_tokens,
        "aborted": aborted,
        "n_cases_run": len(results),
        "tokens_total": sum(r["tokens"] + r["judge_tokens"] for r in results),
        "cost_total_usd_all": sum(r["cost_usd"] + r["judge_cost_usd"] for r in results),
    }


def write_outputs(
    directory: Path, day: date, run: dict, results: list[dict], golden: list, label: str | None = None
) -> list[Path]:
    """Escribe `<stem>.json`, `<stem>.md` y `<stem>-judge-review.md` (mismo stem, sin pisar); devuelve las rutas."""
    from docs_agent.evaluation.metrics import compute_metrics, threshold_sweep
    from docs_agent.evaluation.report import render_judge_review, render_markdown, results_path

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = results_path(directory, day, label=label)
    md_path = json_path.with_suffix(".md")
    review_path = json_path.with_name(f"{json_path.stem}-judge-review.md")
    metrics = compute_metrics(results)
    sweep = threshold_sweep(results)
    payload = {"run": run, "cases": results, "metrics": metrics, "sweep": sweep}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(run, metrics, sweep), encoding="utf-8")
    review_path.write_text(render_judge_review(results, golden), encoding="utf-8")
    return [json_path, md_path, review_path]


def summary_table(run: dict, results: list[dict]) -> Table:
    from docs_agent.evaluation.metrics import compute_metrics
    from docs_agent.evaluation.report import metric_rows

    table = Table(title="docs-agent · evaluación")
    table.add_column("Métrica")
    table.add_column("Valor", justify="right")
    for name, value in metric_rows(run, compute_metrics(results)):
        table.add_row(name, value)
    return table


def exit_code(results: list[dict], aborted: str | None, judge: bool) -> int:
    """2 si paró por presupuesto; 1 si se cayó, si algún caso tiene `error` o, con juez, si el juez falló en algún
    caso por algo que no sea presupuesto (la fidelidad quedaría con menos denominador); 0 si no."""
    if aborted and aborted.startswith(ABORT_CRASH):
        return EXIT_FAILED
    if aborted:
        return EXIT_BUDGET
    if any(r["error"] for r in results):
        return EXIT_FAILED
    if judge and any(r["judge_error"] and r["judge_error"] != "BudgetExceeded" for r in results):
        return EXIT_FAILED
    return 0


# --- ejecución real (OpenAI + servidor MCP por stdio) ---


async def _run(cases, settings, conn, client, judge: bool, max_tokens: int, console: Console, results: list[dict]):
    """Todo en una sola tarea: la sesión MCP se abre y se cierra en la misma (ver `mcp_client`)."""
    from docs_agent.agent.mcp_client import DocsMCPClient, stdio_connect
    from docs_agent.budget import KIND_EVAL

    tools = DocsMCPClient(stdio_connect(settings, KIND_EVAL), settings.mcp_call_timeout_s)
    try:
        # Arranque del servidor fuera del cronómetro (~4 s en Windows); `list_sources` no gasta tokens.
        console.print("[dim]arrancando servidor MCP ...[/]")
        await tools.call("list_sources", {})
        return await run_cases(cases, settings, conn, client, tools, judge, max_tokens, console, results=results)
    finally:
        await tools.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evalúa el grafo con el golden set.")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN, help="ruta del golden set")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS, help="tope de tokens de la corrida")
    parser.add_argument("--only", help="ids separados por coma (p. ej. g01,g05)")
    parser.add_argument("--holdout", action="store_true", help="set de holdout: sin chequeo de distribución y salidas con label")
    parser.add_argument("--no-judge", action="store_true", help="no correr el LLM juez")
    args = parser.parse_args(argv)

    # La consola de Windows (o una tubería en cp1252) no siempre es UTF-8.
    if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    console = Console(width=None if sys.stdout.isatty() else 140)

    from docs_agent.evaluation.golden import GoldenSetError

    # Antes de abrir OpenAI o el servidor MCP: un golden set mal formado no gasta un token.
    try:
        cases = select_cases(args.golden, args.only, holdout=args.holdout)
    except GoldenSetError as exc:
        console.print(Text(f"Golden set inválido: {exc}", style="red"))
        return EXIT_FAILED

    from docs_agent.agent.mcp_client import DocsServerUnavailable, DocsToolError
    from docs_agent.api import make_openai
    from docs_agent.budget import KIND_EVAL, BudgetExceeded, check_budget, daily_limit
    from docs_agent.config import get_settings
    from docs_agent.db import connect
    from docs_agent.evaluation.judge import JUDGE_MODEL
    from docs_agent.rag.retrieve import corpus_size
    from docs_agent.tracing import configure_tracing, load_openai_wrapper

    settings = get_settings()
    if not settings.openai_api_key.get_secret_value():
        console.print("[red]OPENAI_API_KEY no configurada.[/]")
        return EXIT_FAILED

    # Igual que el lifespan de la API (D34): antes de lanzar el servidor stdio, que hereda `os.environ`.
    tracing = configure_tracing(settings)
    wrapper = load_openai_wrapper() if tracing else None
    console.print(f"[dim]tracing LangSmith: {'activo · proyecto ' + settings.langsmith_project if tracing else 'apagado'}[/]")
    judge = not args.no_judge
    if judge and settings.chat_model != JUDGE_MODEL:
        console.print(Text(
            f"aviso: el costo del juez ({JUDGE_MODEL}) se calcula con las tarifas de chat de {settings.chat_model}.",
            style="yellow",
        ))

    results: list[dict] = []  # `run_cases` agrega aquí: si algo inesperado corta la corrida, quedan los parciales
    aborted = None
    crash: BaseException | None = None
    try:
        with connect(settings.database_url) as conn:
            try:
                check_budget(conn, KIND_EVAL, daily_limit(settings, KIND_EVAL))
            except BudgetExceeded as exc:
                console.print(f"[red]Presupuesto diario `eval` agotado: {exc}[/]")
                return EXIT_BUDGET
            if corpus_size(conn, settings.fastapi_docs_ref) == 0:
                console.print("[red]El corpus está vacío: corre primero la ingesta.[/]")
                return EXIT_FAILED
            try:
                _, aborted = asyncio.run(
                    _run(cases, settings, conn, make_openai(wrapper), judge, args.max_tokens, console, results)
                )
            except (DocsServerUnavailable, DocsToolError) as exc:  # en el `list_sources` de arranque
                console.print(Text(f"No se pudo arrancar el servidor MCP ({type(exc).__name__}).", style="red"))
                return EXIT_FAILED
            except (Exception, KeyboardInterrupt) as exc:
                crash = exc
    except psycopg.Error as exc:  # al conectar, o al cerrar la conexión tras un error
        crash = crash or exc

    if crash is not None:
        if isinstance(crash, psycopg.Error):
            # Solo el tipo: el mensaje de libpq puede repetir parte de DATABASE_URL (p. ej. si está mal formada).
            msg = f"Error de base de datos ({type(crash).__name__}). Revisa que Postgres esté arriba y DATABASE_URL."
        else:
            msg = f"La corrida se cortó por un error inesperado ({type(crash).__name__})."
        console.print(Text(msg, style="red"))
        if not results:
            return EXIT_FAILED
        aborted = f"{ABORT_CRASH}:{type(crash).__name__}"

    day = datetime.now(LIMA).date()
    run = build_run_info(settings, day, args.golden, args.only, args.max_tokens, judge, aborted, results)
    paths = write_outputs(RESULTS_DIR, day, run, results, cases, label="holdout" if args.holdout else None)

    console.print()
    console.print(summary_table(run, results))
    if aborted:
        console.print(Text(f"Corrida abortada ({aborted}): {len(results)} de {len(cases)} casos.", style="red"))
    for r in results:
        if r["error"] or r["judge_error"]:
            console.print(Text(f"{r['id']}: error={r['error']} · juez={r['judge_error']}", style="yellow"))
    for p in paths:
        console.print(Text(f"escrito {_display_path(p)}", style="dim"))
    return exit_code(results, aborted, judge)

if __name__ == "__main__":
    sys.exit(main())
