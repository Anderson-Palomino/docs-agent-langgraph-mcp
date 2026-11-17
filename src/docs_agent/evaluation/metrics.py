"""Métricas puras de la evaluación: sin red, sin LLM, sin estado.

Un "caso resultado" es el dict que arma `scripts/evaluate.py` (ver la
Tarea 5). Los casos con `error` quedan fuera de todo salvo `n_errors`.
"""

from urllib.parse import urlsplit, urlunsplit

DEFAULT_THRESHOLDS = (0.48, 0.50, 0.52, 0.55)


def normalize_url(url: str) -> str:
    """Normaliza una URL: `http`->`https`, esquema y host en minúsculas.

    El path conserva mayúsculas y pierde la barra final (el path "/" solo
    queda vacío). La query y el ancla se conservan.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme == "http":
        scheme = "https"
    path = parts.path
    if path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, parts.netloc.lower(), path, parts.query, parts.fragment))


def url_matches(cited: str, expected: str) -> bool:
    """Una cita coincide con la esperada tras normalizar ambas.

    Si la esperada trae `#ancla`, la cita debe ser idéntica; si no, basta
    con que sea la misma página (cualquier ancla).
    """
    c = normalize_url(cited)
    e = normalize_url(expected)
    if "#" in e:
        return c == e
    return c.split("#", 1)[0] == e


def percentile(values: list[float], p: float) -> float | None:
    """Percentil con interpolación lineal (igual que `numpy` por defecto)."""
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * p / 100
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _rate(num: int, den: int) -> dict:
    return {"num": num, "den": den}


def _cites_expected(case: dict) -> bool:
    """Alguna cita coincide con alguna `expected_url`."""
    return any(
        url_matches(ci, e) for ci in case["citations"] for e in case["expected_urls"]
    )


def _ok(cases: list[dict]) -> list[dict]:
    return [c for c in cases if not c.get("error")]


def compute_metrics(cases: list[dict]) -> dict:
    """Calcula las métricas agregadas de una corrida."""
    ok = _ok(cases)
    n_errors = len(cases) - len(ok)

    answer_ok = false_no_se = false_answer = no_se_ok = 0
    for c in ok:
        exp, got = c["expected_route"], c["route"]
        if exp == "either":
            # Ambas rutas valen: no_se siempre; answer solo si cita una esperada.
            if got == "no_se":
                no_se_ok += 1
            elif _cites_expected(c):
                answer_ok += 1
            else:
                false_answer += 1
        elif exp == "answer" and got == "answer":
            answer_ok += 1
        elif exp == "answer":
            false_no_se += 1
        elif got == "answer":
            false_answer += 1
        else:
            no_se_ok += 1

    # "either" respondido cuenta como esperado answer para el acierto de fuente.
    both_answer = [
        c
        for c in ok
        if c["expected_route"] in ("answer", "either") and c["route"] == "answer"
    ]
    hit_any = sum(
        1
        for c in both_answer
        if _cites_expected(c)
    )
    multi = [c for c in both_answer if c["category"] == "in_multi"]
    hit_all = sum(
        1
        for c in multi
        if all(any(url_matches(ci, e) for ci in c["citations"]) for e in c["expected_urls"])
    )

    obtained_answer = [c for c in ok if c["route"] == "answer"]
    grounded = sum(1 for c in obtained_answer if c["grounded"])
    scores = [c["judge"]["score"] for c in obtained_answer if c.get("judge")]

    latencies = [c["latency_ms"] for c in ok]
    judge_cost = sum(c.get("judge_cost_usd") or 0.0 for c in ok)
    total = sum((c.get("cost_usd") or 0.0) + (c.get("judge_cost_usd") or 0.0) for c in ok)

    return {
        "n": len(ok),
        "n_errors": n_errors,
        "route_accuracy": _rate(answer_ok + no_se_ok, len(ok)),
        "confusion": {
            "answer_ok": answer_ok,
            "false_no_se": false_no_se,
            "false_answer": false_answer,
            "no_se_ok": no_se_ok,
        },
        "source_hit_any": _rate(hit_any, len(both_answer)),
        "source_hit_all_multi": _rate(hit_all, len(multi)),
        "grounded_rate": _rate(grounded, len(obtained_answer)),
        "faithfulness_mean": sum(scores) / len(scores) if scores else None,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "cost_total_usd": total,
        "cost_per_question_usd": total / len(ok) if ok else None,
        "judge_cost_usd": judge_cost,
    }


def _cut_by_classifier(case: dict) -> bool:
    return case.get("reason") == "out_of_domain"


def simulate_route(case: dict, threshold: float) -> str:
    """Ruta que habría tomado el grafo con otro umbral de distancia.

    `no_se` si lo cortó el clasificador; si no, `answer` solo si hay
    `best_distance` y es <= umbral.
    """
    if _cut_by_classifier(case):
        return "no_se"
    dist = case.get("best_distance")
    if dist is None or dist > threshold:
        return "no_se"
    return "answer"


def threshold_sweep(
    cases: list[dict], thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS
) -> list[dict]:
    """Tabla offline por umbral, separando clasificador y umbral.

    Un caso con `expected_route="either"` nunca cuenta como falso "no sé" ni
    falso "respondí" y cuenta como correcto en `route_accuracy` sea cual sea
    la ruta simulada: bajo simulación no se conocen las citas, y una
    respuesta solo sería incorrecta si no citara una fuente esperada.
    """
    ok = _ok(cases)
    cut_cls = sum(1 for c in ok if _cut_by_classifier(c))
    fn_cls = sum(
        1 for c in ok if _cut_by_classifier(c) and c["expected_route"] == "answer"
    )
    rows = []
    for t in thresholds:
        cut_thr = fn_thr = fa = correct = 0
        for c in ok:
            sim = simulate_route(c, t)
            if c["expected_route"] == "either":
                correct += 1
                if sim == "no_se" and not _cut_by_classifier(c):
                    cut_thr += 1
                continue
            if sim == "no_se" and not _cut_by_classifier(c):
                cut_thr += 1
                if c["expected_route"] == "answer":
                    fn_thr += 1
            if sim == "answer" and c["expected_route"] == "no_se":
                fa += 1
            if sim == c["expected_route"]:
                correct += 1
        rows.append({
            "threshold": t,
            "cut_by_classifier": cut_cls,
            "cut_by_threshold": cut_thr,
            "false_no_se_classifier": fn_cls,
            "false_no_se_threshold": fn_thr,
            "false_answer": fa,
            "route_accuracy": _rate(correct, len(ok)),
        })
    return rows
