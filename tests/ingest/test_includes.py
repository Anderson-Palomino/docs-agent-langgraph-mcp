from pathlib import Path

import pytest

from docs_agent.ingest.fetch import fetch_docs
from docs_agent.ingest.includes import resolve_includes

SRC = {"x/ten.py": "\n".join(f"L{i}" for i in range(1, 11))}


def inc(spec: str) -> str:
    return f"{{* ../../docs_src/x/ten.py {spec} *}}"


def test_full_file_include():
    out, missing = resolve_includes(f"Antes\n\n{inc('')}\n\nDespués", SRC)
    assert "{*" not in out
    assert "```python\nL1\nL2" in out and "L10\n```" in out
    assert out.startswith("Antes") and out.endswith("Después")
    assert missing == []


def test_ln_ranges_with_gap():
    out, _ = resolve_includes(inc("ln[1:2,5,8:9]"), SRC)
    assert out == "```python\nL1\nL2\n# ...\nL5\n# ...\nL8\nL9\n```"


def test_hl_marks_lines():
    out, _ = resolve_includes(inc("ln[1:3] hl[2]"), SRC)
    assert out == "```python\nL1\nL2  # highlight\nL3\n```"


def test_hl_uses_original_line_numbers():
    out, _ = resolve_includes(inc("ln[5:6] hl[6]"), SRC)
    assert out == "```python\nL5\nL6  # highlight\n```"


def test_missing_file_is_reported():
    out, missing = resolve_includes("{* ../../docs_src/x/missing.py hl[1] *}", SRC)
    assert "[code example: x/missing.py not available]" in out
    assert "```" not in out
    assert missing == ["x/missing.py"]


def test_ln_out_of_range_is_clamped():
    out, _ = resolve_includes(inc("ln[9:99]"), SRC)
    assert out == "```python\nL9\nL10\n```"


def test_text_without_includes_unchanged():
    text = "# Título\n\nUn `{*` suelto no es include.\n"
    assert resolve_includes(text, SRC) == (text, [])


def test_fetch_resolves_real_oauth2_page():
    if not Path("data/fastapi-0.162.0.tar.gz").exists():
        pytest.skip("tarball cacheado ausente")
    docs = fetch_docs("0.162.0")
    page = next(d for d in docs if d.rel_path == "tutorial/security/get-current-user.md")
    assert "OAuth2PasswordBearer" in page.text
    assert "get_current_user" in page.text
    assert "{*" not in page.text
