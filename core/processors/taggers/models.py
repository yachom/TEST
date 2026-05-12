"""온톨로지 태깅 결과 및 Graph 적재 후보 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.shared.domain.asset import AssetFamily, AssetClass
from core.shared.domain.ontology_schema import (
    SignalType,
    InfluenceDirection,
    InfluenceStrength,
    InfluencePeriod,
    Applicability,
    AppliedScope,
)


@dataclass
class OntologyTag:
    article_id: str
    asset_family: AssetFamily
    asset_class: AssetClass
    signal_type: SignalType
    influence_direction: InfluenceDirection
    influence_strength: InfluenceStrength
    influence_period: InfluencePeriod
    applicability: Applicability
    applied_scope: AppliedScope
    affected_evaluation_factors: list[str]    # e.g. ["임대수익률", "공실위험"]
    affected_asset_subtypes: list[str]        # e.g. ["상가", "근린생활시설"]
    event_type: str
    summary: str
    rationale: str
    confidence: float                          # 0.0 ~ 1.0
    tagged_at: datetime = field(default_factory=datetime.utcnow)
    llm_model: str = ""
    raw_llm_response: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class MarketSignalCandidate:
    """OntologyTag → signal_store 적재 전 중간 표현."""
    article_id: str
    tag: OntologyTag
    is_graph_eligible: bool
    ineligible_reason: Optional[str] = None
