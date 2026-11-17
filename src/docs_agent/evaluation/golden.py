"""Golden set de la evaluación (spec 5.1): modelo de caso, carga validada y chequeo de distribución."""

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError, model_validator

Category = Literal[
    "in_basic",
    "in_intermediate",
    "in_multi",
    "out_obvious",
    "out_near",
    "trap_mentioned",
    "trap_ambiguous",
    "trap_missing_fact",
]

# Distribución mínima del spec 5.1.
TOTAL_CASES = 30
IN_CASES = 18
IN_PER_LANG = 9
MIN_IN_MULTI = 2
OUT_CASES = 8
TRAP_CASES = 4
TRAP_TYPES = ("trap_mentioned", "trap_ambiguous", "trap_missing_fact")
JUDGE_REVIEW_CASES = 5


class GoldenSetError(ValueError):
    """Golden set mal formado: se lanza antes de gastar un token."""


class GoldenCase(BaseModel):
    id: str
    question: str
    lang: Literal["es", "en"]
    category: Category
    expected_route: Literal["answer", "no_se"]
    expected_urls: list[str]
    notes: str
    judge_review: bool = False

    @model_validator(mode="after")
    def _route_matches_urls(self) -> "GoldenCase":
        """`answer` necesita URLs esperadas; `no_se` no lleva ninguna; el juez solo revisa casos `answer`."""
        if self.expected_route == "answer" and not self.expected_urls:
            raise ValueError("expected_route=answer requiere al menos una expected_url")
        if self.expected_route == "no_se" and self.expected_urls:
            raise ValueError("expected_route=no_se requiere expected_urls vacía")
        if self.judge_review and self.expected_route != "answer":
            raise ValueError("judge_review solo aplica a casos con expected_route=answer")
        return self


def _first_error(exc: ValidationError) -> str:
    """Primer error de pydantic en una línea (campo: mensaje), sin volcar la excepción entera."""
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"]) or "caso"
    return f"{loc}: {err['msg']}"


def load_golden(path: Path) -> list[GoldenCase]:
    """Lee y valida el golden set; lanza `GoldenSetError` con el id del caso culpable."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldenSetError(f"no se pudo leer el golden set {path}: {exc}") from None
    if not isinstance(raw, list):
        raise GoldenSetError("el golden set debe ser una lista JSON de casos")

    cases: list[GoldenCase] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        case_id = item.get("id", f"#{i}") if isinstance(item, dict) else f"#{i}"
        try:
            case = GoldenCase.model_validate(item)
        except ValidationError as exc:
            raise GoldenSetError(f"caso {case_id}: {_first_error(exc)}") from None
        if case.id in seen:
            raise GoldenSetError(f"id duplicado: {case.id}")
        seen.add(case.id)
        cases.append(case)
    return cases


def check_distribution(cases: list[GoldenCase]) -> list[str]:
    """Problemas de distribución respecto al spec 5.1; lista vacía si el set cumple."""
    problems: list[str] = []
    cats = Counter(c.category for c in cases)
    inside = [c for c in cases if c.category.startswith("in_")]
    n_out = sum(n for cat, n in cats.items() if cat.startswith("out_"))
    n_trap = sum(n for cat, n in cats.items() if cat.startswith("trap_"))

    if len(cases) != TOTAL_CASES:
        problems.append(f"total: {len(cases)} casos, se esperan {TOTAL_CASES}")
    if len(inside) != IN_CASES:
        problems.append(f"in_corpus: {len(inside)} casos in_*, se esperan {IN_CASES}")
    langs = Counter(c.lang for c in inside)
    for lang in ("es", "en"):
        if langs[lang] != IN_PER_LANG:
            problems.append(f"in_corpus {lang}: {langs[lang]} casos, se esperan {IN_PER_LANG}")
    if cats["in_multi"] < MIN_IN_MULTI:
        problems.append(f"in_multi: {cats['in_multi']} casos, se esperan al menos {MIN_IN_MULTI}")

    if n_out != OUT_CASES:
        problems.append(f"out_of_corpus: {n_out} casos out_*, se esperan {OUT_CASES}")
    for cat in ("out_obvious", "out_near"):
        if cats[cat] < 1:
            problems.append(f"{cat}: falta al menos 1 caso")

    if n_trap != TRAP_CASES:
        problems.append(f"trap: {n_trap} casos trap_*, se esperan {TRAP_CASES}")
    for cat in TRAP_TYPES:
        if cats[cat] < 1:
            problems.append(f"{cat}: falta al menos 1 caso")

    n_judge = sum(c.judge_review for c in cases)
    if n_judge != JUDGE_REVIEW_CASES:
        problems.append(f"judge_review: {n_judge} casos, se esperan exactamente {JUDGE_REVIEW_CASES}")
    return problems
