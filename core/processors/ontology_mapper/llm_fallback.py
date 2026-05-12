"""LLMFallbackMapper — 어댑터 미등록 입력을 텍스트 평탄화 후 LLM 호출.

POC: 단순한 평탄화 + 단발 LLM. 추후 다양한 입력(PDF, 웹검색 결과)에 맞춰 정교화.

Prompt + Schema: core.llm.PromptCatalog "mapping.llm_fallback" 에서 로드.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from core.processors.ontology_mapper.base import GraphItem
from core.processors.taggers.models import OntologyTag
from core.shared.domain.asset import AssetClass, AssetFamily
from core.shared.domain.ontology_schema import (
    Applicability,
    AppliedScope,
    InfluenceDirection,
    InfluencePeriod,
    InfluenceStrength,
    SignalType,
)

if TYPE_CHECKING:
    from core.llm.catalog import PromptCatalog
    from core.processors.graph_writers.pattern_builder import GraphPatternBuilder
    from core.shared.infra.llm_client import LLMClient


_PROMPT_KEY = "mapping.llm_fallback"


class LLMFallbackMapper:
    def __init__(
        self,
        llm_client: "LLMClient",
        pattern_builder: "GraphPatternBuilder",
        prompt_catalog: "PromptCatalog",
    ) -> None:
        self._llm = llm_client
        self._builder = pattern_builder
        self._catalog = prompt_catalog

    def map(self, raw: dict) -> list[GraphItem]:
        text = self._flatten_to_text(raw)
        tag = self._call_llm(raw, text)
        return self._builder.build(tag)

    @staticmethod
    def _flatten_to_text(raw: dict) -> str:
        parts: list[str] = []
        for key, value in raw.items():
            if key in {"source_type", "source_id"}:
                continue
            parts.append(f"{key}: {value}")
        return "\n".join(parts)

    def _call_llm(self, raw: dict, text: str) -> OntologyTag:
        rendered = self._catalog.render(_PROMPT_KEY, flattened_text=text)
        response = self._llm.call(rendered.to_llm_request())
        parsed = response.parsed or {}
        return OntologyTag(
            article_id=raw.get("source_id", "unknown"),
            asset_family=AssetFamily.REAL_ESTATE,
            asset_class=AssetClass.COMMERCIAL,
            signal_type=_safe_enum(SignalType, parsed.get("signal_type"), SignalType.MARKET),
            influence_direction=_safe_enum(
                InfluenceDirection, parsed.get("influence_direction"), InfluenceDirection.NEUTRAL
            ),
            influence_strength=_safe_enum(
                InfluenceStrength, parsed.get("influence_strength"), InfluenceStrength.WEAK
            ),
            influence_period=InfluencePeriod.SHORT,
            applicability=Applicability.NEEDS_VERIFICATION,
            applied_scope=AppliedScope.LOCAL,
            affected_evaluation_factors=parsed.get("affected_evaluation_factors", []),
            affected_asset_subtypes=[],
            event_type=parsed.get("event_type", "unknown"),
            summary=parsed.get("summary", text[:120]),
            rationale=parsed.get("rationale", ""),
            confidence=float(parsed.get("confidence", 0.0)),
            tagged_at=datetime.utcnow(),
            llm_model=response.model,
            raw_llm_response=str(parsed),
            extra={"raw_input_keys": list(raw.keys())},
        )


def _safe_enum(enum_cls, value, default):
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default
