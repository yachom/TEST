"""pricing.yaml 로드 + USD 환산 + fallback 동작."""
from __future__ import annotations

from core.llm.pricing import (
    estimate_llm_cost_usd,
    get_price,
    reset_cache,
)


def setup_function(_):
    reset_cache()


def test_known_model_price_loads_from_yaml():
    price = get_price("claude-haiku-4-5")
    assert price.input_usd_per_mtok == 0.80
    assert price.output_usd_per_mtok == 4.0


def test_unknown_model_falls_back():
    price = get_price("totally-made-up-model")
    # fallback 값
    assert price.input_usd_per_mtok == 1.0
    assert price.output_usd_per_mtok == 5.0


def test_cost_estimation_with_anthropic_usage_keys():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    cost = estimate_llm_cost_usd("claude-haiku-4-5", usage)
    # 0.80 + 4.0 = 4.80
    assert abs(cost - 4.80) < 1e-9


def test_cost_estimation_with_openai_usage_keys():
    usage = {"prompt_tokens": 2_000_000, "completion_tokens": 1_000_000}
    cost = estimate_llm_cost_usd("gpt-4o-mini", usage)
    # 2 * 0.15 + 1 * 0.60 = 0.90
    assert abs(cost - 0.90) < 1e-9


def test_cost_estimation_with_no_usage_returns_zero():
    assert estimate_llm_cost_usd("claude-haiku-4-5", None) == 0.0
    assert estimate_llm_cost_usd("claude-haiku-4-5", {}) == 0.0


def test_stub_model_costs_zero():
    cost = estimate_llm_cost_usd("stub", {"input_tokens": 999, "output_tokens": 999})
    assert cost == 0.0
