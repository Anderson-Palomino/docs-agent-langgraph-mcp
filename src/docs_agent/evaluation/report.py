"""Reportes de una corrida de evaluación (spec 5.2, 5.3): Markdown de métricas y archivo de revisión del juez.

Funciones puras sobre los dicts que arma `scripts/evaluate.py`: se pueden regenerar desde el JSON guardado.
"""

from datetime import date
from pathlib import Path

from docs_agent.evaluation.golden import GoldenCase

REVIEW_TEXT_MAX_CHARS = 1_500  # tope de lectura de cada fragmento en la revisión (el juez vio el texto completo)
TRUNCATION_MARK = "[...]"
OWNER_LINE = "Puntaje del dueño (0-1): ___ · Comentario: ___"
NO_VALUE = "—"
FENCE = "````"  # 4 acentos graves: los fragmentos de la doc traen bloques ``` propios


def results_path(directory: Path, day: date, suffix: str = ".json") -> Path:
    """`<día><suffix>`, o `<día>-2<suffix>`, `-3`… si ya existe: nunca pisa una corrida anterior."""
    stem = day.isoformat()
    path = Path(directory) / f"{stem}{suffix}"
    n = 2
    while path.exists():
        path = Path(directory) / f"{stem}-{n}{suffix}"
        n += 1
    return path


# --- Markdown de métricas ---


def _pct(rate: dict) -> str:
    """`85.0% (17/20)`; sin denominador, `— (0/0)`."""
    num, den = rate["num"], rate["den"]
    if not den:
        return f"{NO_VALUE} (0/0)"
    return f"{100 * num / den:.1f}% ({num}/{den})"


def _ms(value: float | None) -> str:
    return NO_VALUE if value is None else f"{value:,.0f} ms"


def _usd(value: float | None) -> str:
    return NO_VALUE if value is None else f"{value:.4f} USD"


def _score(value: float | None) -> str:
    return NO_VALUE if value is None else f"{value:.2f}"


def metric_rows(run: dict, metrics: dict) -> list[tuple[str, str]]:
    """(métrica, valor) en el orden del README; la usan el Markdown y la tabla de consola."""
    c = metrics["confusion"]
    return [
        ("Casos", f"{metrics['n']} casos · {metrics['n_errors']} errores"),
        ("Exactitud de ruta", _pct(metrics["route_accuracy"])),
        (
            "Matriz de ruta",
            f"answer ok {c['answer_ok']} · no_se ok {c['no_se_ok']} · "
            f"falsos \"no sé\" {c['false_no_se']} · falsos \"respondí\" {c['false_answer']}",
        ),
        ("Acierto de fuente (al menos una)", _pct(metrics["source_hit_any"])),
        ("Acierto de fuente in_multi (todas)", _pct(metrics["source_hit_all_multi"])),
        ("Citas válidas (grounded)", _pct(metrics["grounded_rate"])),
        ("Fidelidad (media del juez)", _score(metrics["faithfulness_mean"])),
        ("Respuestas con alguna afirmación no apoyada", _pct(metrics["unsupported_any_rate"])),
        ("Latencia del grafo p50", _ms(metrics["latency_p50_ms"])),
        ("Latencia del grafo p95", _ms(metrics["latency_p95_ms"])),
        ("Costo (casos sin error)", _usd(metrics["cost_total_usd"])),
        ("Costo por pregunta (casos sin error)", _usd(metrics["cost_per_question_usd"])),
        ("Costo del juez (casos sin error)", _usd(metrics["judge_cost_usd"])),
        ("Costo total de la corrida (todos los casos)", _usd(run["cost_total_usd_all"])),
        ("Tokens de la corrida (todos los casos)", f"{run['tokens_total']:,}"),
    ]


def _sweep_table(sweep: list[dict], current: float) -> list[str]:
    lines = [
        "| Umbral | Cortados por clasificador | Cortados por umbral | Falsos \"no sé\" (clasificador) "
        "| Falsos \"no sé\" (umbral) | Falsos \"respondí\" | Exactitud de ruta |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sweep:
        label = f"{r['threshold']:.2f}" + (" (actual)" if abs(r["threshold"] - current) < 1e-9 else "")
        lines.append(
            f"| {label} | {r['cut_by_classifier']} | {r['cut_by_threshold']} | {r['false_no_se_classifier']} "
            f"| {r['false_no_se_threshold']} | {r['false_answer']} | {_pct(r['route_accuracy'])} |"
        )
    return lines


def render_markdown(run: dict, metrics: dict, sweep: list[dict]) -> str:
    """Tabla de métricas (lista para el README) y tabla de umbrales simulados offline (D36)."""
    judge = run["judge_model"] if run.get("judge", True) else "sin juez (--no-judge)"
    lines = [
        f"# Evaluación del {run['date']}",
        "",
        f"Modelo `{run['chat_model']}` · juez `{judge}` · umbral {run['threshold']:.2f} · k={run['top_k']} · "
        f"docs FastAPI {run['docs_ref']} · golden `{run['golden']}`",
    ]
    if run.get("only"):
        lines.append(f"Solo los casos: {', '.join(run['only'])}")
    if run.get("aborted"):
        lines.append(f"**Corrida abortada ({run['aborted']}): resultados parciales.**")
    lines += ["", "## Métricas", "", "| Métrica | Valor |", "|---|---|"]
    lines += [f"| {name} | {value} |" for name, value in metric_rows(run, metrics)]
    lines += ["", "## Umbrales (simulación offline sobre `best_distance`)", ""]
    lines += _sweep_table(sweep, run["threshold"])
    return "\n".join(lines) + "\n"


# --- Revisión del juez ---


def _truncate(text: str, limit: int = REVIEW_TEXT_MAX_CHARS) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + f" {TRUNCATION_MARK}"


def context_fragments(context: str, parts: list[dict]) -> list[tuple[dict, str]]:
    """Corta el contexto exacto del juez en sus fragmentos usando las cabeceras conocidas
    (`[n] título\\nURL: url\\n`, ver `rag.answer.build_context`)."""
    headers = [f"[{p['n']}] {p['title']}\nURL: {p['url']}\n" for p in parts]
    starts: list[int] = []
    pos = 0
    for h in headers:
        i = context.find(h, pos)
        if i < 0:
            return [(parts[0], context)] if parts else []  # no debería pasar: todo el texto, sin cortar
        starts.append(i)
        pos = i + len(h)
    out = []
    for k, (p, h, start) in enumerate(zip(parts, headers, starts)):
        end = starts[k + 1] if k + 1 < len(starts) else len(context)
        out.append((p, context[start + len(h) : end]))
    return out


def _judge_lines(case: dict) -> list[str]:
    j = case.get("judge")
    if not j:
        return [f"**Juez:** sin juicio ({case.get('judge_error') or 'no se corrió el juez'})."]
    lines = [f"**Puntaje del juez:** {j['score']:.2f}", "", "**Afirmaciones:**", ""]
    lines += [f"- {'✓' if c['supported'] else '✗'} {c['text']}" for c in j.get("claims", [])] or ["- (ninguna)"]
    lines += ["", f"**Motivo del juez:** {j['reason']}"]
    return lines


def _case_section(g: GoldenCase, case: dict | None) -> list[str]:
    lines = [f"## {g.id} — {g.question}", ""]
    if case is None:
        return lines + ["Este caso no se corrió (filtrado con `--only` o corrida abortada).", "", OWNER_LINE, ""]
    reason = f" ({case['reason']})" if case.get("reason") else ""
    lines += [f"Ruta esperada: `{g.expected_route}` · obtenida: `{case.get('route')}`{reason}", ""]
    if case.get("error"):
        return lines + [f"El caso terminó con error: `{case['error']}`.", "", OWNER_LINE, ""]
    if case.get("route") != "answer":
        return lines + [f"El grafo respondió `{case.get('route')}`{reason}: no hay respuesta que juzgar.", "", OWNER_LINE, ""]

    lines += ["### Fragmentos que vio el modelo", ""]
    for part, text in context_fragments(case.get("judge_context") or "", case.get("context_parts") or []):
        kind = "sección completa (get_section)" if part.get("section") else "fragmento"
        lines += [f"**[{part['n']}] {part['title']}** · {kind} · {part['url']}", "", f"{FENCE}text", _truncate(text), FENCE, ""]
    titles = {p["url"]: p["title"] for p in case.get("context_parts") or []}
    lines += ["### Respuesta", "", case.get("answer") or "", "", "**Citas:**", ""]
    lines += [f"- {titles.get(u, u)} · {u}" for u in case.get("citations") or []] or ["- (ninguna)"]
    lines += [""] + _judge_lines(case) + ["", OWNER_LINE, ""]
    return lines


def render_judge_review(cases: list[dict], golden: list[GoldenCase]) -> str:
    """Una sección por caso `judge_review` del golden set, en su orden, para que el dueño puntúe rápido."""
    by_id = {c["id"]: c for c in cases}
    review = [g for g in golden if g.judge_review]
    lines = [
        "# Revisión humana del juez",
        "",
        f"{len(review)} casos `judge_review`. Los fragmentos se muestran truncados a ~{REVIEW_TEXT_MAX_CHARS} "
        f"caracteres para leer (`{TRUNCATION_MARK}`); el juez recibió el texto completo. Escribe tu puntaje "
        "(0-1) en cada línea del dueño.",
        "",
    ]
    for g in review:
        lines += _case_section(g, by_id.get(g.id))
    return "\n".join(lines)
