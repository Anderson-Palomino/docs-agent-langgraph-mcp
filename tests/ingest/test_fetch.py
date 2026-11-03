import io
import tarfile

import pytest

from docs_agent.ingest.fetch import (
    _docs_from_tarball,
    heading_anchor,
    path_to_url,
)


def make_tarball(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            raw = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
    return buf.getvalue()


@pytest.mark.parametrize(
    "rel,url",
    [
        ("index.md", "https://fastapi.tiangolo.com/"),
        ("tutorial/body.md", "https://fastapi.tiangolo.com/tutorial/body/"),
        ("advanced/index.md", "https://fastapi.tiangolo.com/advanced/"),
    ],
)
def test_path_to_url(rel, url):
    assert path_to_url(rel) == url


def test_heading_anchor_explicit_id():
    assert heading_anchor("Request Body { #request-body }") == (
        "Request Body",
        "request-body",
    )


def test_heading_anchor_slugified():
    assert heading_anchor("Import `BaseModel`!") == (
        "Import `BaseModel`!",
        "import-basemodel",
    )


def test_tarball_filters_language_and_exclusions(tmp_path):
    data = make_tarball(
        {
            "fastapi-0.0.0/docs/en/docs/tutorial/body.md": "# Body",
            "fastapi-0.0.0/docs/en/docs/release-notes.md": "# Notes",
            "fastapi-0.0.0/docs/es/docs/tutorial/body.md": "# Cuerpo",
            "fastapi-0.0.0/README.md": "x",
        }
    )
    docs = _docs_from_tarball(data)
    assert [d.rel_path for d in docs] == ["tutorial/body.md"]
    assert docs[0].url == "https://fastapi.tiangolo.com/tutorial/body/"
