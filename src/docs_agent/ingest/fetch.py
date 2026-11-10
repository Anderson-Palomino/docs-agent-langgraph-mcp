"""Descarga la doc de FastAPI (tag fijo) y mapea cada archivo a su URL pública."""

import io
import re
import sys
import tarfile
import unicodedata
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

import httpx

from docs_agent.ingest.includes import resolve_includes

BASE_URL = "https://fastapi.tiangolo.com/"
TARBALL_URL = "https://codeload.github.com/fastapi/fastapi/tar.gz/refs/tags/{ref}"

# Patrones glob (sobre rel_path) de páginas sin valor para responder preguntas técnicas.
EXCLUDED: tuple[str, ...] = (
    "release-notes.md",
    "management*.md",
    "fastapi-people.md",
    "contributing.md",
    "external-links.md",
    "newsletter.md",
    "help-fastapi.md",
    "translation-banner.md",
    "_llm-test.md",  # página interna para probar traducciones con LLM
)

_DOCS_MARKER = "/docs/en/docs/"
_SRC_MARKER = "/docs_src/"
_INCLUDE_COUNT = re.compile(r"\{\*\s*\S+\s*.*?\s*\*\}")
_ATTR_ID = re.compile(r"\s*\{\s*#([^\s}]+)[^}]*\}\s*$")


@dataclass(frozen=True)
class DocFile:
    rel_path: str  # relativo a docs/en/docs/, separado por "/"
    url: str
    text: str


def path_to_url(rel_path: str) -> str:
    """`tutorial/body.md` -> BASE_URL + `tutorial/body/`; los `index.md` mapean a su carpeta."""
    stem = rel_path.removesuffix(".md")
    if stem == "index":
        return BASE_URL
    stem = stem.removesuffix("/index")
    return f"{BASE_URL}{stem}/"


def _slugify(text: str) -> str:
    """Slug estilo MkDocs `toc` (python-markdown): ascii, minúsculas, sin símbolos."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def heading_anchor(heading_text: str) -> tuple[str, str]:
    """Devuelve `(título_limpio, ancla)`; respeta `{ #id }` (attr_list) si existe."""
    m = _ATTR_ID.search(heading_text)
    if m:
        return heading_text[: m.start()].rstrip(), m.group(1)
    title = heading_text.strip()
    return title, _slugify(title)


def _is_excluded(rel_path: str) -> bool:
    return any(fnmatch(rel_path, pat) for pat in EXCLUDED)


def _docs_from_tarball(data: bytes) -> list[DocFile]:
    docs: list[DocFile] = []
    src_files: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            top, sep, src_rel = member.name.partition(_SRC_MARKER)
            if sep and "/" not in top:
                f = tar.extractfile(member)
                if f is not None:
                    try:
                        src_files[src_rel] = f.read().decode("utf-8")
                    except UnicodeDecodeError:
                        pass
                continue
            if not member.name.endswith(".md"):
                continue
            top, sep, rel_path = member.name.partition(_DOCS_MARKER)
            # Solo el directorio raíz del tarball puede preceder a docs/en/docs/
            if not sep or "/" in top or _is_excluded(rel_path):
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            text = f.read().decode("utf-8")
            docs.append(DocFile(rel_path, path_to_url(rel_path), text))
    resolved = 0
    missing_total: list[str] = []
    out: list[DocFile] = []
    for d in docs:
        text, missing = resolve_includes(d.text, src_files)
        resolved += len(_INCLUDE_COUNT.findall(d.text)) - len(missing)
        missing_total.extend(missing)
        out.append(DocFile(d.rel_path, d.url, text))
    print(
        f"resolved {resolved} includes, {len(missing_total)} missing",
        file=sys.stderr,
    )
    return sorted(out, key=lambda d: d.rel_path)


def fetch_docs(ref: str, cache_dir: Path = Path("data")) -> list[DocFile]:
    cache = cache_dir / f"fastapi-{ref}.tar.gz"
    if cache.exists():
        data = cache.read_bytes()
    else:
        resp = httpx.get(
            TARBALL_URL.format(ref=ref), follow_redirects=True, timeout=120.0
        )
        resp.raise_for_status()
        data = resp.content
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    return _docs_from_tarball(data)
