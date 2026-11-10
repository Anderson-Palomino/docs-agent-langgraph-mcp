import pytest

from docs_agent.config import Settings
from docs_agent.pricing import cost_usd, total_tokens

SETTINGS = Settings(_env_file=None)


def test_price_defaults():
    assert SETTINGS.price_chat_input_per_mtok == 0.40
    assert SETTINGS.price_chat_output_per_mtok == 1.60
    assert SETTINGS.price_embedding_per_mtok == 0.02


def test_cost_usd_known_values():
    assert cost_usd({"prompt_tokens": 1_000_000}, SETTINGS) == pytest.approx(0.40)
    assert cost_usd({"embedding_tokens": 1_000_000}, SETTINGS) == pytest.approx(0.02)
    assert cost_usd({"completion_tokens": 1_000_000}, SETTINGS) == pytest.approx(1.60)


def test_cost_usd_classifier_split_and_total():
    # Con desglose (estado del grafo): entrada y salida a su tarifa.
    split = {"classifier_prompt_tokens": 1_000_000, "classifier_completion_tokens": 1_000_000}
    assert cost_usd(split, SETTINGS) == pytest.approx(0.40 + 1.60)
    # Solo el total (forma de `/ask`): a tarifa de entrada.
    assert cost_usd({"classifier_tokens": 1_000_000}, SETTINGS) == pytest.approx(0.40)


def test_total_tokens_sums_graph_usage():
    usage = {
        "classifier_prompt_tokens": 10,
        "classifier_completion_tokens": 2,
        "embedding_tokens": 7,
        "prompt_tokens": 100,
        "completion_tokens": 30,
    }
    assert total_tokens(usage) == 149
    assert total_tokens({}) == 0


def test_cost_usd_classifier_total_ignored_when_split_present():
    usage = {
        "classifier_prompt_tokens": 1_000_000,
        "classifier_completion_tokens": 0,
        "classifier_tokens": 1_000_000,
    }
    assert cost_usd(usage, SETTINGS) == pytest.approx(0.40)
    assert total_tokens(usage) == 1_000_000
