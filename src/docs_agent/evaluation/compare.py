"""Comparación antes/después de dos corridas de evaluación (spec 5.2, 5.2bis), más el holdout aparte.

Funciones puras sobre los JSON que escribe `scripts/evaluate.py` (`{"run", "cases", "metrics", "sweep"}`).
Las métricas agregadas salen de `metrics.compute_metrics` (se recalculan desde `cases`). Las filas
anteriores a la Tarea 3 no traen `language`/`search_query`/`translated`: se muestran como "—".
"""

from docs_agent.evaluation.metrics import _cites_expected, _rate, compute_metrics
from docs_agent.evaluation.report import NO_VALUE, _ms, _pct, _score, _usd

DETAIL_IDS = ["g03", "g06", "g07", "g09"]  # las 4 preguntas en español que el 11-17 respondieron "no sé"
OUT_OF_CORPUS_ROUTES = ("no_se", "either")
CLASSIFIER_RULE = (
    "«Ruta del clasificador» cuenta los casos `answer` (acierta si no los corta) y los `no_se` de categoría "
    "`out_*` o `trap_mentioned` (acierta si los corta); los demás `trap_*`, los `either` y los casos con "
    "error quedan fuera: esos le tocan al umbral."
)


def _ok(cases: list[dict]) -> list[dict]:
    return [c for c in cases if not c.get("error")]


def _is_cut(case: dict) -> bool:
    return case.get("reason") == "out_of_domain"


def _classifier_should_cut(case: dict) -> bool:
    cat = case.get("category") or ""
    return cat.startswith("out_") or cat == "trap_mentioned"


def classifier_accuracy(cases: list[dict]) -> dict:
    """Acierto del clasificador (formato `_rate`), ver `CLASSIFIER_RULE`."""
    num = den = 0
    for c in _ok(cases):
        if c["expected_route"] == "answer":
            den += 1
            num += not _is_cut(c)
        elif c["expected_route"] == "no_se" and _classifier_should_cut(c):
            den += 1
            num += _is_cut(c)
    return _rate(num, den)


def classifier_flips(before: list[dict], after: list[dict]) -> list[dict]:
    """Casos (sin error en ambas corridas) cuya decisión del clasificador cambió, en el orden de `after`."""
    prev = {c["id"]: c for c in _ok(before)}
    flips = []
    for c in _ok(after):
        b = prev.get(c["id"])
        if b is not None and _is_cut(b) != _is_cut(c):
            flips.append({
                "id": c["id"], "expected_route": c["expected_route"],
                "before_cut": _is_cut(b), "after_cut": _is_cut(c),
            })
    return flips


def _cut_by(case: dict | None) -> str | None:
    """Quién dijo "no sé": `classifier`, `threshold` (umbral/contexto insuficiente) o `None` si respondió."""
    if case is None or case.get("error"):
        return None
    if _is_cut(case):
        return "classifier"
    if case.get("route") == "no_se":
        return "threshold"
    return None


def _route_status(case: dict | None) -> str | None:
    """`false_answer`, `false_no_se` o `None` (acierto, error o caso faltante), igual que `compute_metrics`."""
    if case is None or case.get("error"):
        return None
    exp, got = case["expected_route"], case.get("route")
    if exp == "either":
        return "false_answer" if got == "answer" and not _cites_expected(case) else None
    if exp == "answer" and got != "answer":
        return "false_no_se"
    if exp == "no_se" and got == "answer":
        return "false_answer"
    return None


def route_changes(before: list[dict], after: list[dict]) -> list[dict]:
    """Casos cuya ruta, quién cortó o condición de falso «no sé»/«respondí» cambió entre corridas.

    Deja ver caso por caso el criterio (2) de la spec 5.2bis: un falso «respondí» nuevo no se esconde
    detrás de otro corregido aunque el conteo total quede igual.
    """
    b_by, a_by = {c["id"]: c for c in before}, {c["id"]: c for c in after}
    out = []
    for cid in _ordered_ids(before, after, lambda c: True):
        b, a = b_by.get(cid), a_by.get(cid)
        item = {
            "id": cid,
            "lang": _field(a, "lang") or _field(b, "lang"),
            "expected_route": _field(a, "expected_route") or _field(b, "expected_route"),
            "route_before": _field(b, "route"),
            "route_after": _field(a, "route"),
            "cut_by_before": _cut_by(b),
            "cut_by_after": _cut_by(a),
            "status_before": _route_status(b),
            "status_after": _route_status(a),
        }
        if any(item[f"{k}_before"] != item[f"{k}_after"] for k in ("route", "cut_by", "status")):
            out.append(item)
    return out


_STATUS_LABEL = {"false_answer": "falso «respondí»", "false_no_se": "falso «no sé»"}


def _change_mark(item: dict) -> str:
    """`nuevo falso «respondí»`, `corrige falso «no sé»`… o "—" si no cambió la condición."""
    sb, sa = item["status_before"], item["status_after"]
    if sb == sa:
        return NO_VALUE
    marks = []
    if sa:
        marks.append(f"**nuevo {_STATUS_LABEL[sa]}**")
    if sb:
        marks.append(f"corrige {_STATUS_LABEL[sb]}")
    return " · ".join(marks)


def _ordered_ids(before: list[dict], after: list[dict], keep) -> list[str]:
    """Ids que cumplen `keep` en cualquiera de las corridas: primero el orden de `before`, luego los nuevos."""
    ids: list[str] = []
    for c in before + after:
        if keep(c) and c["id"] not in ids:
            ids.append(c["id"])
    return ids


def _field(case: dict | None, key: str):
    return None if case is None else case.get(key)


def es_out_of_corpus_rows(before: list[dict], after: list[dict]) -> list[dict]:
    """Preguntas en español que no deberían responderse (`no_se`) o pueden no hacerlo (`either`)."""
    b_by, a_by = {c["id"]: c for c in before}, {c["id"]: c for c in after}
    ids = _ordered_ids(
        before, after, lambda c: c.get("lang") == "es" and c.get("expected_route") in OUT_OF_CORPUS_ROUTES
    )
    rows = []
    for cid in ids:
        b, a = b_by.get(cid), a_by.get(cid)
        d_b, d_a = _field(b, "best_distance"), _field(a, "best_distance")
        rows.append({
            "id": cid,
            "route_before": _field(b, "route"),
            "route_after": _field(a, "route"),
            "cut_by_before": _cut_by(b),
            "cut_by_after": _cut_by(a),
            "distance_before": d_b,
            "distance_after": d_a,
            "closer": None if d_b is None or d_a is None else d_a < d_b,
        })
    return rows


def case_detail(before: list[dict], after: list[dict], ids: list[str]) -> list[dict]:
    """Distancia, ruta, consulta usada y fuentes de los `ids` antes y después."""
    b_by, a_by = {c["id"]: c for c in before}, {c["id"]: c for c in after}
    out = []
    for cid in ids:
        b, a = b_by.get(cid), a_by.get(cid)
        out.append({
            "id": cid,
            "question": _field(a, "question") or _field(b, "question"),
            "distance_before": _field(b, "best_distance"),
            "distance_after": _field(a, "best_distance"),
            "route_before": _field(b, "route"),
            "route_after": _field(a, "route"),
            "search_query_after": _field(a, "search_query"),
            "retrieved_after": _field(a, "retrieved_urls"),
        })
    return out


# --- Markdown ---


def _cost_without_judge(cases: list[dict]) -> float | None:
    ok = _ok(cases)
    return sum(c.get("cost_usd") or 0.0 for c in ok) / len(ok) if ok else None


def _summary_rows(cases: list[dict]) -> list[tuple[str, str]]:
    """(métrica, valor) de una corrida, en el orden de la spec 5.2."""
    m = compute_metrics(cases)
    conf = m["confusion"]
    faith = m["faithfulness_n"]
    return [
        ("Casos", f"{m['n']} sin error · {m['n_errors']} con error"),
        ("Ruta", _pct(m["route_accuracy"])),
        ("Ruta del clasificador", _pct(classifier_accuracy(cases))),
        ("Falsos «no sé»", str(conf["false_no_se"])),
        ("Falsos «respondí»", str(conf["false_answer"])),
        ("Citas válidas", _pct(m["grounded_rate"])),
        ("Acierto de fuente", _pct(m["source_hit_any"])),
        ("Fidelidad", f"{_score(m['faithfulness_mean'])} ({faith['num']}/{faith['den']} juzgadas)"),
        ("Latencia p50", _ms(m["latency_p50_ms"])),
        ("Latencia p95", _ms(m["latency_p95_ms"])),
        ("Costo por pregunta (sin juez)", _usd(_cost_without_judge(cases))),
        ("Costo por pregunta (con juez)", _usd(m["cost_per_question_usd"])),
    ]


def _cell(value) -> str:
    """Celda de tabla: `None` → "—"; sin `|` ni saltos de línea que rompan la tabla."""
    if value is None or value == "" or value == []:
        return NO_VALUE
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, list):
        return "<br>".join(_cell(v) for v in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


_CUT_LABEL = {"classifier": "clasificador", "threshold": "umbral"}


def _cut_cell(value: str | None) -> str:
    return _CUT_LABEL.get(value, NO_VALUE)


def _run_label(run: dict) -> str:
    r = run.get("run") or {}
    threshold = r.get("threshold")
    thr = f" · umbral {threshold:.2f}" if isinstance(threshold, (int, float)) else ""
    return f"`{r.get('date', NO_VALUE)}` (`{r.get('chat_model', NO_VALUE)}`{thr})"


def _expected_routes(*case_lists: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cases in case_lists:
        for c in cases:
            out.setdefault(c["id"], c.get("expected_route"))
    return out


def render_comparison(before_run: dict, after_run: dict, holdout_run: dict | None) -> str:
    """Markdown con la tabla antes/después, el español fuera del corpus, el detalle de g03/g06/g07/g09 y,
    si hay, el holdout en una tabla propia (nunca sumado a la del golden set)."""
    before, after = before_run["cases"], after_run["cases"]
    lines = [
        "# Comparación antes/después",
        "",
        f"Antes: {_run_label(before_run)} · después: {_run_label(after_run)}. Métricas recalculadas desde los "
        "casos con `compute_metrics`.",
        "",
        "## Golden set",
        "",
        "| Métrica | Antes | Después |",
        "|---|---|---|",
    ]
    lines += [
        f"| {name} | {vb} | {va} |"
        for (name, vb), (_, va) in zip(_summary_rows(before), _summary_rows(after))
    ]
    lines += ["", CLASSIFIER_RULE, "", "### Cambios del clasificador", ""]
    flips = classifier_flips(before, after)
    if flips:
        lines += ["| Caso | Ruta esperada | Antes | Después |", "|---|---|---|---|"]
        lines += [
            f"| {f['id']} | {f['expected_route']} | {'cortado' if f['before_cut'] else 'pasa'} "
            f"| {'cortado' if f['after_cut'] else 'pasa'} |"
            for f in flips
        ]
    else:
        lines.append("Ningún caso cambió de decisión en el clasificador.")

    lines += [
        "",
        "### Cambios de ruta",
        "",
        "Todos los casos cuya ruta, quién cortó o condición de falso «no sé»/«respondí» cambió (cualquier "
        "idioma): un falso «respondí» nuevo aparece aunque el conteo total no cambie.",
        "",
    ]
    changes = route_changes(before, after)
    if changes:
        lines += [
            "| Caso | Idioma | Ruta esperada | Ruta antes | Ruta después | Cortó antes | Cortó después | Cambio |",
            "|---|---|---|---|---|---|---|---|",
        ]
        lines += [
            f"| {c['id']} | {_cell(c['lang'])} | {_cell(c['expected_route'])} | {_cell(c['route_before'])} "
            f"| {_cell(c['route_after'])} | {_cut_cell(c['cut_by_before'])} | {_cut_cell(c['cut_by_after'])} "
            f"| {_change_mark(c)} |"
            for c in changes
        ]
    else:
        lines.append("Ningún caso cambió de ruta, de quién cortó ni de condición.")

    expected = _expected_routes(after, before)
    lines += [
        "",
        "## Español fuera del corpus",
        "",
        "Preguntas `es` con ruta esperada `no_se` (o `either`, donde ambas rutas valen). Distancia antes: con la "
        "pregunta original; después: con la consulta que usó el grafo (la traducción).",
        "",
        "| Caso | Esperada | Ruta antes | Cortó antes | Ruta después | Cortó después | Distancia antes "
        "| Distancia después | ¿Más cerca del corpus? |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in es_out_of_corpus_rows(before, after):
        lines.append(
            f"| {r['id']} | {_cell(expected.get(r['id']))} | {_cell(r['route_before'])} "
            f"| {_cut_cell(r['cut_by_before'])} | {_cell(r['route_after'])} | {_cut_cell(r['cut_by_after'])} "
            f"| {_cell(r['distance_before'])} | {_cell(r['distance_after'])} | {_cell(r['closer'])} |"
        )

    lines += [
        "",
        f"## Detalle de {', '.join(DETAIL_IDS)}",
        "",
        "| Caso | Pregunta | Distancia antes | Distancia después | Ruta antes | Ruta después "
        "| Consulta usada (después) | Fuentes (después) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in case_detail(before, after, DETAIL_IDS):
        lines.append(
            f"| {d['id']} | {_cell(d['question'])} | {_cell(d['distance_before'])} | {_cell(d['distance_after'])} "
            f"| {_cell(d['route_before'])} | {_cell(d['route_after'])} | {_cell(d['search_query_after'])} "
            f"| {_cell(d['retrieved_after'])} |"
        )

    if holdout_run is not None:
        lines += _holdout_lines(holdout_run)
    return "\n".join(lines) + "\n"


def _holdout_lines(holdout_run: dict) -> list[str]:
    cases = holdout_run["cases"]
    lines = [
        "",
        "## Holdout (prompt congelado, una corrida)",
        "",
        f"Corrida {_run_label(holdout_run)}. Tabla aparte: no se suma al golden set.",
        "",
        "| Métrica | Valor |",
        "|---|---|",
    ]
    lines += [f"| {name} | {value} |" for name, value in _summary_rows(cases)]
    lines += [
        "",
        "### Holdout: español fuera del corpus",
        "",
        "| Caso | Esperada | Ruta | Cortó | Distancia | Consulta usada |",
        "|---|---|---|---|---|---|",
    ]
    for c in cases:
        if c.get("lang") == "es" and c.get("expected_route") in OUT_OF_CORPUS_ROUTES:
            lines.append(
                f"| {c['id']} | {c['expected_route']} | {_cell(c.get('route'))} | {_cut_cell(_cut_by(c))} "
                f"| {_cell(c.get('best_distance'))} | {_cell(c.get('search_query'))} |"
            )
    return lines
