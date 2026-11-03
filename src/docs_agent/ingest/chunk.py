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


def _overlap_tail(content: str, overlap_tokens: int) -> str:
    if overlap_tokens <= 0:
        return ""
    tokens = encode(content)
    if len(tokens) <= overlap_tokens:
        return content
    tail = decode(tokens[-overlap_tokens:])
    # evita arrancar a media palabra
    if content.endswith(tail) and not content[-len(tail) - 1].isspace():
        parts = tail.split(None, 1)
        tail = parts[1] if len(parts) > 1 else ""
    return tail.lstrip("�")


def _pack(blocks: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    pieces: list[str] = []
    prefix = ""
    cur: list[str] = []

    def render(items: list[str]) -> str:
        body = "\n\n".join(items)
        return f"{prefix}\n\n{body}" if prefix else body

    for block in blocks:
        if cur and count_tokens(render([*cur, block])) > max_tokens:
            piece = render(cur)
            pieces.append(piece)
            prefix = _overlap_tail(piece, overlap_tokens)
            cur = []
        cur.append(block)
    if cur:
        pieces.append(render(cur))
    return pieces


def chunk_document(
    doc: DocFile, max_tokens: int = 800, overlap_tokens: int = 100
) -> list[Chunk]:
    page_title = _page_title(doc.text, doc.rel_path)
    chunks: list[Chunk] = []
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
        if not has_body:
            continue
        content = "\n\n".join(blocks)
        pieces = (
            [content]
            if count_tokens(content) <= max_tokens
            else _pack(blocks, max_tokens, overlap_tokens)
        )
        chunks.extend(Chunk(url, title, p, count_tokens(p)) for p in pieces)
    return chunks
