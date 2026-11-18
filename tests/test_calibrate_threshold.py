"""Modo `--from-results` de `scripts/calibrate_threshold.py`: sin OpenAI ni base de datos."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "calibrate_threshold.py"


def _load():
    spec = importlib.util.spec_from_file_location("calibrate_threshold", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(cid, expected, route, reason, dist, urls, error=None):
    return {
        "id": cid, "question": f"pregunta {cid}", "expected_route": expected, "route": route,
        "reason": reason, "best_distance": dist, "retrieved_urls": urls, "error": error,
    }


def test_from_results_escribe_tablas_ordenadas_y_excluye_errores(tmp_path):
    cases = [
        _case("q2", "no_se", "no_se", "insufficient_context", 0.61, ["https://x/b"]),
        _case("q1", "answer", "answer", None, 0.30, ["https://x/a", "https://x/c"]),
        _case("q3", "no_se", "no_se", "out_of_domain", None, [], error="boom"),
        _case("q4", "either", "no_se", "out_of_domain", 0.90, []),
    ]
    run = {"date": "2026-11-18", "threshold": 0.52, "top_k": 4, "docs_ref": "0.115.0", "chat_model": "m"}
    src = tmp_path / "run.json"
    src.write_text(json.dumps({"run": run, "cases": cases, "metrics": {}, "sweep": []}), encoding="utf-8")
    out = tmp_path / "out.md"

    module = _load()
    module.from_results(src, out)

    text = out.read_text(encoding="utf-8")
    assert "run.json" in text and "2026-11-18" in text
    assert "| id | Pregunta | Esperada | Clasificador | Mejor distancia | URL |" in text
    assert text.index("| q1 |") < text.index("| q2 |") < text.index("| q4 |")
    assert "| q1 | pregunta q1 | answer | aceptó | 0.3000 | https://x/a |" in text
    assert "| q4 | pregunta q4 | either | rechazó | 0.9000 | - |" in text
    assert "| q3 |" not in text.split("## Umbrales")[0].split("Excluidos")[0]
    assert "q3" in text.split("Excluidos")[1]
    assert "Cortados por clasificador" in text and "Cortados por umbral" in text
    assert "(actual)" in text
    assert "faithfulness" in text and "either" in text
