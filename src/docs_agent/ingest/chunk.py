"""Trocea una página Markdown por encabezados `##`/`###`, con tope de tokens."""

import re
from dataclasses import dataclass

from docs_agent.ingest.fetch import DocFile, heading_anchor
from docs_agent.tokens import count_tokens, decode, encode

_FENCE = re.compile(r"^\s*(`{3,})")
_HEADING = re.compile(r"^(#{1,3}) +(\S.*)$")


@dataclass(frozen=True)
class Chunk:
    url: str
    title: str
    content: str
    token_count: int


@dataclass(frozen=True)
class Section:
    url: str
    title: str
    content: str


def _fence_ticks(line: str, open_ticks: int) -> int:
    """Nuevo estado de bloque de código (0 = fuera) tras procesar `line`."""
    m = _FENCE.match(line)
    if not m:
        return open_ticks
    n = len(m.group(1))
    if open_ticks == 0:
        return n
    # cierra solo con una fence de al menos las mismas comillas y sin info string
    if n >= open_ticks and line.strip() == "`" * n:
        return 0
    return open_ticks


def _split_sections(text: str) -> list[tuple[str | None, list[str]]]:
    """Lista de (encabezado `##`/`###` o None para la intro, líneas incluido el encabezado)."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    ticks = 0
    for line in text.splitlines():
        was_in_fence = ticks > 0
        ticks = _fence_ticks(line, ticks)
        m = None if was_in_fence or ticks else _HEADING.match(line)
        if m and len(m.group(1)) >= 2:
            sections.append((m.group(2), [line]))
        else:
            sections[-1][1].append(line)
    return sections


def _page_title(text: str, fallback: str) -> str:
    ticks = 0
    for line in text.splitlines():
        was_in_fence = ticks > 0
        ticks = _fence_ticks(line, ticks)
        if not was_in_fence and not ticks:
            m = _HEADING.match(line)
            if m and len(m.group(1)) == 1:
                return heading_anchor(m.group(2))[0]
    return fallback


def _paragraphs(lines: list[str]) -> list[str]:
    """Bloques separados por líneas en blanco; los bloques de código no se parten."""
    blocks: list[str] = []
    cur: list[str] = []
    ticks = 0
    for line in lines:
        ticks = _fence_ticks(line, ticks)
        if not line.strip() and not ticks:
            if cur:
                blocks.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


_CONTINUED = "# (continued)"


def _join(lines: list[str]) -> str:
    return "\n".join(lines)


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _split_oversized(block: str, max_tokens: int) -> list[str]:
    """Parte un bloque mayor que el tope por líneas (y por tokens si una línea sola no cabe).

    Si el corte cae dentro de un bloque de código, el trozo se cierra con la misma fence
    y el siguiente la reabre seguida de `# (continued)`.
    """
    if count_tokens(block) <= max_tokens:
        return [block]
    out: list[str] = []
    cur: list[str] = []
    header = 0  # líneas de reapertura al inicio de `cur` (fence + `# (continued)`)
    ticks, open_line = 0, ""

    def closing(t: int, ol: str) -> list[str]:
        return [_indent(ol) + "`" * t] if t else []

    def emit() -> None:
        nonlocal cur, header
        out.append(_join(cur + closing(ticks, open_line)))
        cur = [open_line, _indent(open_line) + _CONTINUED] if ticks else []
        header = len(cur)

    for line in block.split("\n"):
        new_ticks = _fence_ticks(line, ticks)
        new_open = line if not ticks and new_ticks else open_line
        tail = closing(new_ticks, new_open)
        if len(cur) > header and count_tokens(_join([*cur, line, *tail])) > max_tokens:
            emit()
        if count_tokens(_join([*cur, line, *tail])) > max_tokens:
            # una línea que no cabe sola: se parte por tokens
            tokens = encode(line)
            while tokens:
                k = len(tokens)
                while k > 1 and count_tokens(
                    _join([*cur, decode(tokens[:k]), *tail])
                ) > max_tokens:
                    k -= 1
                cur.append(decode(tokens[:k]))
                tokens = tokens[k:]
                if tokens:
                    emit()
        else:
            cur.append(line)
        ticks, open_line = new_ticks, new_open
    if len(cur) > header:
        out.append(_join(cur))
    return out


def _overlap_tail(content: str, overlap_tokens: int) -> str:
    if overlap_tokens <= 0:
        return ""
    tokens = encode(content)
    if len(tokens) <= overlap_tokens:
        tail = content
    else:
        tail = decode(tokens[-overlap_tokens:])
        # evita arrancar a media palabra
        if content.endswith(tail) and not content[-len(tail) - 1].isspace():
            parts = tail.split(None, 1)
            tail = parts[1] if len(parts) > 1 else ""
        tail = tail.lstrip("�")
    # nunca se toma solape de dentro de (ni a través de) un bloque de código
    if "```" in tail:
        return ""
    ticks = 0
    for line in content[: len(content) - len(tail)].splitlines():
        ticks = _fence_ticks(line, ticks)
    return "" if ticks else tail


def _pack(blocks: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    """Acumula bloques hasta `max_tokens`, contando el prefijo de solape en el tope."""
    pieces: list[str] = []
    prefix = ""
    cur: list[str] = []

    def render(items: list[str]) -> str:
        body = "\n\n".join(items)
        return f"{prefix}\n\n{body}" if prefix else body

    for block in (b for blk in blocks for b in _split_oversized(blk, max_tokens)):
        if cur and count_tokens(render([*cur, block])) > max_tokens:
            piece = render(cur)
            pieces.append(piece)
            prefix = _overlap_tail(piece, overlap_tokens)
            cur = []
        if not cur and prefix and count_tokens(render([block])) > max_tokens:
            prefix = ""
        cur.append(block)
    if cur:
        pieces.append(render(cur))
    return pieces


def _sections(doc: DocFile) -> list[tuple[str, str, list[str], list[str]]]:
    """(url, título, líneas, bloques) de cada intro/`##`/`###` con cuerpo."""
    page_title = _page_title(doc.text, doc.rel_path)
    out: list[tuple[str, str, list[str], list[str]]] = []
    for heading, lines in _split_sections(doc.text):
        blocks = _paragraphs(lines)
        if heading is None:
            url, title = doc.url, page_title
            # la intro lleva el H1; sin más texto no aporta nada
            has_body = any(not _HEADING.match(b) or b.count("\n") for b in blocks)
        else:
            clean, anchor = heading_anchor(heading)
            url, title = f"{doc.url}#{anchor}", f"{page_title} > {clean}"
            has_body = len(blocks) > 1 or (blocks and "\n" in blocks[0])
        if has_body:
            out.append((url, title, lines, blocks))
    return out


def split_sections(doc: DocFile) -> list[Section]:
    """Secciones completas (encabezado + cuerpo, sin tope), con las URLs de los fragmentos."""
    return [
        Section(url, title, _join(lines).strip("\n"))
        for url, title, lines, _ in _sections(doc)
    ]


def chunk_document(
    doc: DocFile, max_tokens: int = 800, overlap_tokens: int = 100
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for url, title, _, blocks in _sections(doc):
        content = "\n\n".join(blocks)
        pieces = (
            [content]
            if count_tokens(content) <= max_tokens
            else _pack(blocks, max_tokens, overlap_tokens)
        )
        chunks.extend(Chunk(url, title, p, count_tokens(p)) for p in pieces)
    return chunks
