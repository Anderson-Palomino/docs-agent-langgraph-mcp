from docs_agent.ingest.chunk import chunk_document
from docs_agent.ingest.fetch import DocFile
from docs_agent.tokens import count_tokens

DOC = DocFile(
    "tutorial/body.md",
    "https://fastapi.tiangolo.com/tutorial/body/",
    "# Request Body\n\nIntro text.\n\n## Import `BaseModel` { #import-basemodel }\n\n"
    "```python\n# this is a comment, not a heading\nfrom pydantic import BaseModel\n```\n\n"
    "### Create your data model\n\nDeclare it.\n",
)


def test_splits_on_h2_h3_and_keeps_intro():
    chunks = chunk_document(DOC)
    assert [c.url for c in chunks] == [
        "https://fastapi.tiangolo.com/tutorial/body/",
        "https://fastapi.tiangolo.com/tutorial/body/#import-basemodel",
        "https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model",
    ]
    assert chunks[0].title == "Request Body"
    assert chunks[1].title == "Request Body > Import `BaseModel`"
    assert chunks[1].content.startswith("## Import `BaseModel`")


def test_comment_inside_code_fence_is_not_a_heading():
    chunks = chunk_document(DOC)
    assert "# this is a comment" in chunks[1].content
    assert len(chunks) == 3


def test_h2_inside_four_backtick_and_indented_fence_is_ignored():
    doc = DocFile(
        "a.md",
        "https://fastapi.tiangolo.com/a/",
        "# A { #a }\n\nIntro.\n\n/// note\n\n    ````md\n    ```python\n    ## fake\n    ```\n"
        "    ## fake2\n    ````\n\n///\n\n## Real\n\nBody.\n",
    )
    chunks = chunk_document(doc)
    assert [c.url for c in chunks] == [
        "https://fastapi.tiangolo.com/a/",
        "https://fastapi.tiangolo.com/a/#real",
    ]
    assert chunks[0].title == "A"
    assert "## fake2" in chunks[0].content


def test_heading_only_sections_are_omitted():
    doc = DocFile(
        "a.md", "https://x/a/", "# A\n\n## Empty\n\n### Full\n\nText.\n"
    )
    assert [c.url for c in chunk_document(doc)] == ["https://x/a/#full"]


def test_missing_h1_falls_back_to_rel_path():
    doc = DocFile("a.md", "https://x/a/", "Intro.\n\n## S\n\nText.\n")
    chunks = chunk_document(doc)
    assert chunks[0].title == "a.md"
    assert chunks[1].title == "a.md > S"


def test_oversized_section_is_split_with_overlap():
    paras = [" ".join(f"p{p}w{i}" for i in range(60)) for p in range(8)]
    doc = DocFile(
        "a.md",
        "https://fastapi.tiangolo.com/a/",
        "# A\n\n## Big\n\n" + "\n\n".join(paras) + "\n",
    )
    chunks = [
        c
        for c in chunk_document(doc, max_tokens=400, overlap_tokens=50)
        if c.url.endswith("#big")
    ]
    assert len(chunks) >= 2
    assert all(c.token_count <= 400 + 50 for c in chunks)
    assert all(c.title == "A > Big" for c in chunks)
    tail_of_first = chunks[0].content.split()[-5:]
    assert " ".join(tail_of_first) in chunks[1].content
    # el 2º arranca con un sufijo del 1º (de al menos 5 palabras)
    w1, w2 = chunks[0].content.split(), chunks[1].content.split()
    k = next(k for k in range(len(w2), 0, -1) if w1[-k:] == w2[:k])
    assert k >= 5


def test_oversized_code_block_keeps_every_line():
    # D24: un bloque mayor que el tope se parte por líneas (antes se dejaba entero, D16)
    code = "```python\n" + "\n\n".join(f"x{i} = {i}" for i in range(300)) + "\n```"
    doc = DocFile("a.md", "https://x/a/", f"# A\n\n## S\n\nBefore.\n\n{code}\n")
    chunks = chunk_document(doc, max_tokens=100, overlap_tokens=10)
    assert all(count_tokens(c.content) <= 100 for c in chunks)
    for c in chunks:
        fences = [ln for ln in c.content.splitlines() if ln.lstrip().startswith("```")]
        assert len(fences) % 2 == 0, c.content
    lines = {ln for c in chunks for ln in c.content.splitlines()}
    assert all(f"x{i} = {i}" in lines for i in range(300))
    with_code = [c for c in chunks if "```python" in c.content]
    assert len(with_code) >= 2
    for c in with_code[1:]:
        assert c.content.splitlines()[:2] == ["```python", "# (continued)"]


def test_token_count_matches_counter():
    for c in chunk_document(DOC):
        assert c.token_count == count_tokens(c.content)


def _fence_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("```"))


def _words(n: int, tag: str) -> str:
    return " ".join(f"{tag}w{i}" for i in range(n))


def test_chunks_never_exceed_cap_including_overlap():
    paras = [_words(25, f"p{p}") for p in range(20)]
    doc = DocFile(
        "a.md", "https://x/a/", "# A\n\n## Big\n\n" + "\n\n".join(paras) + "\n"
    )
    chunks = chunk_document(doc, max_tokens=120, overlap_tokens=30)
    assert len(chunks) >= 3
    assert all(count_tokens(c.content) <= 120 for c in chunks)


def test_code_block_not_split():
    code = "```python\n" + "\n".join(f"value_{i} = compute({i})" for i in range(10)) + "\n```"
    assert 60 <= count_tokens(code) <= 100
    body = "\n\n".join([code, _words(25, "a"), _words(25, "b"), _words(25, "c")])
    doc = DocFile("a.md", "https://x/a/", f"# A\n\n## S\n\n{body}\n")
    chunks = chunk_document(doc, max_tokens=120, overlap_tokens=30)
    assert len(chunks) >= 2
    assert any(code in c.content for c in chunks)
    for c in chunks:
        assert _fence_lines(c.content) % 2 == 0, c.content
        assert count_tokens(c.content) <= 120


def test_oversized_code_block_split_by_lines():
    code = "```python\n" + "\n".join(f"value_{i} = compute({i})" for i in range(40)) + "\n```"
    assert 250 <= count_tokens(code) <= 400
    doc = DocFile("a.md", "https://x/a/", f"# A\n\n## S\n\nBefore.\n\n{code}\n")
    chunks = chunk_document(doc, max_tokens=120, overlap_tokens=30)
    with_code = [c for c in chunks if "```python" in c.content]
    assert len(with_code) >= 2
    for c in chunks:
        assert _fence_lines(c.content) % 2 == 0, c.content
        assert count_tokens(c.content) <= 120
    lines = with_code[1].content.splitlines()
    assert lines[0] == "```python"
    assert lines[1] == "# (continued)"
    # no se pierde ninguna línea de código
    joined = "\n".join(c.content for c in chunks)
    assert all(f"value_{i} = compute({i})" in joined for i in range(40))


def test_sections_match_chunk_urls():
    from docs_agent.ingest.chunk import split_sections

    doc = DocFile(
        "a.md",
        "https://x/a/",
        "# A\n\nIntro.\n\n## Empty\n\n### Full { #full-id }\n\nText.\n\n## Big\n\n"
        + "\n\n".join(_words(25, f"p{p}") for p in range(20))
        + "\n",
    )
    for d in (DOC, doc):
        sections = split_sections(d)
        chunks = chunk_document(d, max_tokens=120, overlap_tokens=30)
        assert {s.url for s in sections} == {c.url for c in chunks}
        assert {(s.url, s.title) for s in sections} == {(c.url, c.title) for c in chunks}
        assert len({s.url for s in sections}) == len(sections)
    big = next(s for s in split_sections(doc) if s.url.endswith("#big"))
    assert big.content.startswith("## Big")
    assert "p19w24" in big.content
