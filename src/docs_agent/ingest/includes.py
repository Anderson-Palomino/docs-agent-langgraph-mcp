"""Resuelve los includes `{* ../../docs_src/... ln[..] hl[..] *}` de la doc de FastAPI."""

import re

_INCLUDE = re.compile(r"\{\*\s*(\S+)\s*(.*?)\s*\*\}")
_PREFIX = "../../docs_src/"
_ARG = re.compile(r"(ln|hl)\[([^\]]*)\]")


def _ranges(spec: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        a, _, b = part.partition(":")
        try:
            start = int(a)
            end = int(b) if b else start
        except ValueError:
            continue
        out.append((start, end))
    return out


def _render(lines: list[str], args: str) -> str:
    opts = {k: v for k, v in _ARG.findall(args)}
    total = len(lines)
    highlighted: set[int] = set()
    for a, b in _ranges(opts.get("hl", "")):
        highlighted.update(range(a, b + 1))
    if "ln" in opts:
        ranges = [(max(a, 1), min(b, total)) for a, b in _ranges(opts["ln"])]
        ranges = [(a, b) for a, b in ranges if a <= b]
    else:
        ranges = []
    if not ranges:
        ranges = [(1, total)]
    out: list[str] = []
    for i, (a, b) in enumerate(ranges):
        if i:
            out.append("# ...")
        for n in range(a, b + 1):
            line = lines[n - 1]
            out.append(f"{line}  # highlight" if n in highlighted else line)
    return "```python\n" + "\n".join(out) + "\n```"


def resolve_includes(text: str, src_files: dict[str, str]) -> tuple[str, list[str]]:
    """Devuelve `(texto, rutas_no_resueltas)`; `src_files` es relativo a `docs_src/`."""
    missing: list[str] = []

    def repl(m: re.Match[str]) -> str:
        path = m.group(1).removeprefix(_PREFIX)
        content = src_files.get(path)
        if content is None:
            missing.append(path)
            return f"[code example: {path} not available]"
        return _render(content.splitlines(), m.group(2))

    return _INCLUDE.sub(repl, text), missing
