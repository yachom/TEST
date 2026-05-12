"""LLM 모델 토큰 단가 로드 + USD 환산.

policy.py 의 _MODEL_PRICING_USD_PER_1M_TOKENS 를 yaml 로 이주.
PolicyGate, TracingLLMClient(추후) 둘 다 이 모듈을 통해 비용을 계산한다.

캐싱: 모듈 로드 시 1회 yaml 파싱, 이후 메모리 dict 로 조회.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


_PRICING_PATH = Path(__file__).parent / "pricing.yaml"


@dataclass(frozen=True)
class ModelPrice:
    input_usd_per_mtok: float
    output_usd_per_mtok: float


_pricing_cache: dict[str, ModelPrice] | None = None
_fallback_cache: ModelPrice | None = None


def _load() -> tuple[dict[str, ModelPrice], ModelPrice]:
    global _pricing_cache, _fallback_cache
    if _pricing_cache is not None and _fallback_cache is not None:
        return _pricing_cache, _fallback_cache

    if not _PRICING_PATH.exists():
        _pricing_cache = {}
        _fallback_cache = ModelPrice(1.0, 5.0)
        return _pricing_cache, _fallback_cache

    with open(_PRICING_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    models_raw = raw.get("models", {}) or {}
    _pricing_cache = {
        name: ModelPrice(
            input_usd_per_mtok=float(cfg.get("input_usd_per_mtok", 0.0)),
            output_usd_per_mtok=float(cfg.get("output_usd_per_mtok", 0.0)),
        )
        for name, cfg in models_raw.items()
    }

    fb = raw.get("fallback", {}) or {}
    _fallback_cache = ModelPrice(
        input_usd_per_mtok=float(fb.get("input_usd_per_mtok", 1.0)),
        output_usd_per_mtok=float(fb.get("output_usd_per_mtok", 5.0)),
    )
    return _pricing_cache, _fallback_cache


def get_price(model: str) -> ModelPrice:
    """모델명을 받아 단가 반환. 매핑 없으면 fallback."""
    pricing, fallback = _load()
    return pricing.get(model, fallback)


def estimate_llm_cost_usd(model: str, usage: Optional[dict]) -> float:
    """LLMResponse.usage 를 USD 비용으로 환산.

    usage 키는 provider 별 표기 차이 흡수:
      input_tokens / prompt_tokens
      output_tokens / completion_tokens
    """
    if not usage:
        return 0.0
    price = get_price(model)
    in_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    out_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    return (
        in_tokens * price.input_usd_per_mtok
        + out_tokens * price.output_usd_per_mtok
    ) / 1_000_000.0


def reset_cache() -> None:
    """테스트용 — yaml 변경 후 재로드."""
    global _pricing_cache, _fallback_cache
    _pricing_cache = None
    _fallback_cache = None
