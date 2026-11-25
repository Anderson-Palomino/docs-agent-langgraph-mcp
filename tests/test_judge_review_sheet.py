"""`scripts/judge_review_sheet.py`: genera la hoja del juez y calcula la coincidencia; sin red ni base."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "judge_review_sheet.py"
REAL_RUN = ROOT / "eval" / "results" / "2026-11-17.json"
A = "https://fastapi.tiangolo.com/tutorial/body/"
MARKED = ["g01", "g02", "g10", "g12", "g16", "g30"]


@pytest.fixture(scope="module")
def sheet():
    spec = importlib.util.spec_from_file_location("judge_review_sheet", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(cid: str, route: str = "answer") -> dict:
    ok = route == "answer"
    return {
        "id": cid, "question": f"q {cid}", "route": route, "reason": None, "error": None,
        "answer": "resp" if ok else None, "citations": [A] if ok else [],
        "judge_context": f"[1] T\nURL: {A}\ntexto" if ok else None,
        "context_parts": [{"n": 1, "title": "T", "url": A, "section": False}] if ok else [],
        "judge": {"score": 1.0, "unsupported_claims": [], "reason": "ok",
                  "claims": [{"text": "c1", "supported": True}]} if ok else None,
        "judge_error": None,
    }


def write_results(path: Path, ids: list[str], no_se: tuple[str, ...] = ()) -> Path:
    cases = [case(i, "no_se" if i in no_se else "answer") for i in ids]
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return path


def test_main_escribe_hoja_con_marcados_y_extras(sheet, tmp_path):
    res = write_results(tmp_path / "r.json", MARKED + ["g03", "g06", "g07", "g09"], no_se=("g06",))
    out = tmp_path / "hoja.md"
    assert sheet.main([str(res), "--out", str(out), "--extra", "g03,g06,g07,g09"]) == 0
    md = out.read_text(encoding="utf-8")
    heads = [line.split()[1] for line in md.splitlines() if line.startswith("## ")]
    assert heads == MARKED + ["g03", "g07", "g09"]  # g06 respondió no_se: no aparece


def test_main_mas_de_10_avisa_y_no_escribe(sheet, tmp_path, capsys):
    res = write_results(tmp_path / "r.json", MARKED + ["g03", "g06", "g07", "g09", "g04"])
    out = tmp_path / "hoja.md"
    assert sheet.main([str(res), "--out", str(out), "--extra", "g03,g06,g07,g09,g04"]) == 1
    assert not out.exists()
    assert "10" in capsys.readouterr().out


def test_main_extra_desconocido_falla(sheet, tmp_path):
    res = write_results(tmp_path / "r.json", MARKED)
    out = tmp_path / "hoja.md"
    assert sheet.main([str(res), "--out", str(out), "--extra", "g99"]) == 1
    assert not out.exists()


def test_main_score_imprime_coincidencia(sheet, tmp_path, capsys):
    res = write_results(tmp_path / "r.json", MARKED)
    out = tmp_path / "hoja.md"
    assert sheet.main([str(res), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8").replace("| 1 | c1 | apoyada | | |", "| 1 | c1 | apoyada | sí | |", 3)
    out.write_text(text, encoding="utf-8")
    capsys.readouterr()
    assert sheet.main(["--score", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "3 de 6" in printed  # afirmaciones respondidas
    assert "100.0%" in printed  # las 3 respondidas coinciden


def test_main_score_lista_filas_problematicas_y_total_intacto(sheet, tmp_path, capsys):
    res = write_results(tmp_path / "r.json", ["g01", "g02"])
    out = tmp_path / "hoja.md"
    sheet.main([str(res), "--out", str(out)])
    lines = out.read_text(encoding="utf-8").splitlines()
    rows = [i for i, line in enumerate(lines) if line.startswith("| 1 | c1 |")]
    lines[rows[0]] = "| 1 | c1 | apoyada | sí"  # sin barra final ni nota: cuenta
    lines[rows[1]] = "| 1 | c1 | apoyada | sí. | |"  # valor no reconocido
    out.write_text("\n".join(lines), encoding="utf-8")
    capsys.readouterr()
    assert sheet.main(["--score", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "1 de 2" in printed  # total sigue en 2
    assert "g02 #1: valor no reconocido «sí.»" in printed
    assert "g01 #1" not in printed


def test_main_score_sin_respuestas(sheet, tmp_path, capsys):
    res = write_results(tmp_path / "r.json", MARKED)
    out = tmp_path / "hoja.md"
    sheet.main([str(res), "--out", str(out)])
    capsys.readouterr()
    assert sheet.main(["--score", str(out)]) == 0
    assert "0 de 6" in capsys.readouterr().out


@pytest.mark.skipif(not REAL_RUN.exists(), reason="sin la corrida real")
def test_hoja_sobre_corrida_real(sheet, tmp_path):
    out = tmp_path / "hoja.md"
    assert sheet.main([str(REAL_RUN), "--out", str(out), "--extra", "g03,g06,g07,g09"]) == 0
    assert "| # | Afirmación | Juez | ¿De acuerdo? (sí/no) | Nota |" in out.read_text(encoding="utf-8")
