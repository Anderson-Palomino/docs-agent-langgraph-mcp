"""Reportes de una corrida de evaluación (spec 5.2, 5.3): Markdown de métricas y hoja de revisión del juez (sí/no por afirmación).

Funciones puras sobre los dicts que arma `scripts/evaluate.py`: se pueden regenerar desde el JSON guardado.
"""

import re
from datetime import date
from pathlib import Path

from docs_agent.evaluation.golden import GoldenCase

REVIEW_TEXT_MAX_CHARS = 1_500  # tope de lectura de cada fragmento en la revisión (el juez vio el texto completo)
TRUNCATION_MARK = "[...]"
AGREE_COLUMN = "¿De acuerdo? (sí/no)"
REVIEW_HEADER = f"| # | Afirmación | Juez | {AGREE_COLUMN} | Nota |"
CLAIMS_HEADING = "### Afirmaciones del juez"
NOT_ANSWERED_NOTE = "no se respondió en esta corrida"
MAX_REVIEW_CASES = 10  # tope de casos de la hoja (spec 5.6): el dueño la llena en ~20 min
NO_VALUE = "—"
FENCE = "````"  # 4 acentos graves: los fragmentos de la doc traen bloques ``` propios


def results_path(directory: Path, day: date, suffix: str = ".json", label: str | None = None) -> Path:
    """`<día>[-<label>]<suffix>`, o `…-2<suffix>`, `-3`… si ya existe: nunca pisa una corrida anterior."""
    stem = f"{day.isoformat()}-{label}" if label else day.isoformat()
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


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _cases(metrics: dict) -> str:
    """`30 casos (28 sin error · 2 errores)`."""
    n, errors = metrics["n"], metrics["n_errors"]
    return f"{_plural(n + errors, 'caso', 'casos')} ({n} sin error · {_plural(errors, 'error', 'errores')})"


def _faithfulness(metrics: dict) -> str:
    """`0.87 (20 juzgadas / 22 respondidas)`: el denominador deja ver si el juez falló en algún caso."""
    fn = metrics["faithfulness_n"]
    judged = _plural(fn["num"], "juzgada", "juzgadas")
    answered = _plural(fn["den"], "respondida", "respondidas")
    return f"{_score(metrics['faithfulness_mean'])} ({judged} / {answered})"


def metric_rows(run: dict, metrics: dict) -> list[tuple[str, str]]:
    """(métrica, valor) en el orden del README; la usan el Markdown y la tabla de consola."""
    c = metrics["confusion"]
    return [
        ("Casos", _cases(metrics)),
        ("Exactitud de ruta", _pct(metrics["route_accuracy"])),
        (
            "Matriz de ruta",
            f"answer ok {c['answer_ok']} · no_se ok {c['no_se_ok']} · "
            f"falsos \"no sé\" {c['false_no_se']} · falsos \"respondí\" {c['false_answer']}",
        ),
        ("Acierto de fuente (al menos una)", _pct(metrics["source_hit_any"])),
        ("Acierto de fuente in_multi (todas)", _pct(metrics["source_hit_all_multi"])),
        ("Citas válidas (grounded)", _pct(metrics["grounded_rate"])),
        ("Fidelidad (media del juez)", _faithfulness(metrics)),
        ("Respuestas con alguna afirmación no apoyada", _pct(metrics["unsupported_any_rate"])),
        ("Latencia del grafo p50", _ms(metrics["latency_p50_ms"])),
        ("Latencia del grafo p95", _ms(metrics["latency_p95_ms"])),
        ("Costo (casos sin error)", _usd(metrics["cost_total_usd"])),
        ("Costo por pregunta (casos sin error)", _usd(metrics["cost_per_question_usd"])),
        ("Costo del juez (casos sin error)", _usd(metrics["judge_cost_usd"])),
        ("Costo total de la corrida (todos los casos)", _usd(run["cost_total_usd_all"])),
        ("Tokens de la corrida (todos los casos)", f"{run['tokens_total']:,}"),
    ]


def sweep_table(sweep: list[dict], current: float) -> list[str]:
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
    if run.get("judge") and run.get("judge_model") != run.get("chat_model"):
        lines.append(f"Aviso: el costo del juez usa las tarifas de `{run['chat_model']}`, no las de `{run['judge_model']}`.")
    lines += ["", "## Métricas", "", "| Métrica | Valor |", "|---|---|"]
    lines += [f"| {name} | {value} |" for name, value in metric_rows(run, metrics)]
    lines += ["", "## Umbrales (simulación offline sobre `best_distance`)", ""]
    lines += sweep_table(sweep, run["threshold"])
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


def _cell(text: str) -> str:
    """Texto de una celda de tabla Markdown: sin saltos de línea y con `|` escapado."""
    return " ".join(text.split()).replace("|", "\\|")


def _no_answer_section(g: GoldenCase, case: dict | None) -> list[str]:
    """Caso de la hoja que no tiene respuesta que revisar: nota y sin tabla."""
    lines = [f"## {g.id} — {g.question}", ""]
    if case is None:
        why = "el caso no se corrió (filtrado con `--only` o corrida abortada)"
    elif case.get("error"):
        why = f"el caso terminó con error `{case['error']}`"
    elif case.get("route") != "answer":
        reason = f" ({case['reason']})" if case.get("reason") else ""
        why = f"el grafo respondió `{case.get('route')}`{reason}"
    else:
        why = None
    if why is not None:
        return lines + [f"Nota: {NOT_ANSWERED_NOTE} — {why}.", ""]
    return []


def _claims_table(case: dict) -> list[str]:
    j = case.get("judge")
    if not j:
        return [f"El juez no emitió juicio ({case.get('judge_error') or 'no se corrió el juez'}): nada que revisar.", ""]
    claims = j.get("claims") or []
    if not claims:
        return ["El juez no extrajo afirmaciones de esta respuesta: nada que revisar.", ""]
    lines = [REVIEW_HEADER, "|---|---|---|---|---|"]
    for n, c in enumerate(claims, start=1):
        verdict = "apoyada" if c["supported"] else "no apoyada"
        lines.append(f"| {n} | {_cell(c['text'])} | {verdict} | | |")
    return lines + [""]


def _case_section(g: GoldenCase, case: dict | None) -> list[str]:
    if case is None or case.get("error") or case.get("route") != "answer":
        return _no_answer_section(g, case)
    reason = f" ({case['reason']})" if case.get("reason") else ""
    lines = [f"## {g.id} — {g.question}", ""]
    lines += [f"Ruta esperada: `{g.expected_route}` · obtenida: `{case.get('route')}`{reason}", ""]
    lines += ["### Respuesta del modelo", "", case.get("answer") or "", "", "**Citas:**", ""]
    titles = {p["url"]: p["title"] for p in case.get("context_parts") or []}
    lines += [f"- {titles.get(u, u)} · {u}" for u in case.get("citations") or []] or ["- (ninguna)"]
    lines += ["", CLAIMS_HEADING, ""] + _claims_table(case)
    lines += ["### Contexto que vio el modelo", ""]
    for part, text in context_fragments(case.get("judge_context") or "", case.get("context_parts") or []):
        kind = "sección completa (get_section)" if part.get("section") else "fragmento"
        lines += [f"**[{part['n']}] {part['title']}** · {kind} · {part['url']}", "", f"{FENCE}text", _truncate(text), FENCE, ""]
        lines += ["<details>", "<summary>Texto completo</summary>", "", f"{FENCE}text", text.strip(), FENCE, "", "</details>", ""]
    return lines


def review_case_ids(cases: list[dict], golden: list[GoldenCase], extra_ids: list[str]) -> list[str]:
    """Ids de la hoja: los `judge_review` del golden set en su orden (aunque no se respondan) y después los
    `extra_ids` solo si su ruta fue `answer` (los que verán los entrevistadores)."""
    by_id = {c["id"]: c for c in cases}
    ids = [g.id for g in golden if g.judge_review]
    known = {g.id for g in golden}
    for cid in extra_ids:
        case = by_id.get(cid)
        if cid in known and cid not in ids and case is not None and case.get("route") == "answer" and not case.get("error"):
            ids.append(cid)
    return ids


def render_judge_review(cases: list[dict], golden: list[GoldenCase], extra_ids: list[str]) -> str:
    """Hoja para que el dueño marque, afirmación por afirmación, si coincide con el juez (sí/no + nota).

    El puntaje se calcula después con `parse_review` + `score_review`; el dueño nunca puntúa en 0-1."""
    by_id = {c["id"]: c for c in cases}
    by_golden = {g.id: g for g in golden}
    ids = review_case_ids(cases, golden, extra_ids)
    lines = [
        "# Revisión humana del juez",
        "",
        f"{_plural(len(ids), 'caso', 'casos')}. En cada tabla, la columna `{AGREE_COLUMN}` es tuya: escribe `sí` si la afirmación "
        "está bien juzgada (apoyada o no por el contexto) y `no` si el juez se equivocó; la nota es opcional. "
        f"Los fragmentos muestran un extracto de ~{REVIEW_TEXT_MAX_CHARS} caracteres (`{TRUNCATION_MARK}`); "
        "el texto completo que vio el juez está en el bloque plegable de cada fragmento largo.",
        "",
    ]
    for cid in ids:
        lines += _case_section(by_golden[cid], by_id.get(cid))
    return "\n".join(lines)


PROBLEM_UNREADABLE = "fila ilegible"
PROBLEM_UNANSWERED = "sin responder"
PROBLEM_UNRECOGNIZED = "valor no reconocido"  # p. ej. "sí." o "sí, pero…": no se adivina, el dueño lo corrige


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())]


def _agree(cell: str) -> bool | None:
    value = cell.strip().casefold()
    if value in ("sí", "si"):
        return True
    if value == "no":
        return False
    return None  # vacía o ilegible: sin respuesta


def parse_review(markdown: str) -> list[dict]:
    """Filas `{case_id, n, agree}` de una hoja (llena o no), en orden. `agree`: True/False/None (sin responder).

    Ignora los bloques ```` (fragmentos del contexto, que pueden traer `##` o tablas propias)."""
    rows: list[dict] = []
    case_id: str | None = None
    in_fence = in_claims = False
    for line in markdown.splitlines():
        if line.startswith(FENCE):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        head = re.match(r"## ([A-Za-z]+\d+) — ", line)
        if head:
            case_id, in_claims = head.group(1), False
            continue
        if line.startswith("#"):  # solo se leen filas bajo `### Afirmaciones del juez` (no la respuesta del modelo)
            in_claims = line.strip() == CLAIMS_HEADING
            continue
        if case_id is None or not in_claims or not line.lstrip().startswith("|"):
            continue
        num = re.match(r"\|\s*(\d+)\b", line.strip())
        if not num:
            continue  # cabecera, separador o texto suelto
        # Celdas tras la barra inicial: [n, afirmación, juez, ¿de acuerdo?, nota?]; la barra final y la nota
        # pueden faltar (el dueño las borra al escribir). Si no llega ni la columna de acuerdo, la fila es ilegible.
        cells = _split_row(line.strip()[1:])
        row = {"case_id": case_id, "n": int(num.group(1)), "agree": None, "raw": "", "problem": PROBLEM_UNREADABLE}
        if len(cells) >= 4:
            row.update(agree=_agree(cells[3]), raw=cells[3], problem=None)
            if row["agree"] is None:
                row["problem"] = PROBLEM_UNANSWERED if not cells[3] else PROBLEM_UNRECOGNIZED
        rows.append(row)
    return rows


def score_review(rows: list[dict]) -> dict:
    """Conteos de coincidencia entre el dueño y el juez; sin porcentajes, así no hay división por cero.

    Un caso está respondido si todas sus afirmaciones tienen sí/no, y de acuerdo si además todas son "sí"."""
    by_case: dict[str, list[bool | None]] = {}
    for r in rows:
        by_case.setdefault(r["case_id"], []).append(r["agree"])
    answered = [v for v in by_case.values() if all(a is not None for a in v)]
    return {
        "claims_answered": sum(r["agree"] is not None for r in rows),
        "claims_total": len(rows),
        "claims_agree": sum(r["agree"] is True for r in rows),
        "case_agree": sum(all(v) for v in answered),
        "cases_answered": len(answered),
        "cases_total": len(by_case),
    }
