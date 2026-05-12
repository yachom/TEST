"""EvaluationOrchestrator — 3축 EvaluationStrategy 통합 호출.

확장 자리. 현재는 placeholder (`DefaultEvaluationOrchestrator`) 로 빈 list 반환.
추후 실제 점수 산출 로직이 ScoreBuilder 에 채워지면 그대로 활성화된다.

흐름 (의도):
    analyze(address) → Orchestrator → ReportBuilder
                                    → EvaluationOrchestrator.evaluate(asset_id, profile, scope_id)
                                          → SentimentStrategy.evaluate()
                                          → QuantitativeStrategy.evaluate()
                                          → StructuralStrategy.evaluate()
                                    → AnalysisResult.claims

`AssetProfile.evaluation_dimensions` 에 따라 호출할 strategy 결정 — 자산이
요구한 차원만 평가.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.evaluation.base import EvaluationStrategy
    from core.shared.domain.evaluation import AssetProfile, EvaluationClaim, EvaluationDimension


class EvaluationOrchestrator(ABC):
    """3축 평가의 통합 진입점.

    구현체는 자산이 요구한 dimension 들의 strategy 를 호출하여 claim 을 모은다.
    """

    @abstractmethod
    def evaluate(
        self,
        asset_id: str,
        profile: "AssetProfile",
        scope_id: str | None = None,
    ) -> list["EvaluationClaim"]: ...


class DefaultEvaluationOrchestrator(EvaluationOrchestrator):
    """기본 구현 — dimension 별 strategy registry 에서 호출.

    POC 시점에서는 SentimentEvaluationStrategy 가 stub score (0.0) 만 반환하고,
    Quantitative/Structural 도 stub. 그래도 claim 객체는 정상 생성되므로
    AnalysisResult.claims 가 빈 list 가 아닌 형태로 들어간다 — 향후 구현 swap 시
    호출 측 변경 0.
    """

    def __init__(
        self,
        strategies: dict["EvaluationDimension", "EvaluationStrategy"] | None = None,
    ) -> None:
        self._strategies = strategies or {}

    def evaluate(
        self,
        asset_id: str,
        profile: "AssetProfile",
        scope_id: str | None = None,
    ) -> list["EvaluationClaim"]:
        claims: list = []
        for dimension in profile.evaluation_dimensions:
            strategy = self._strategies.get(dimension)
            if strategy is None:
                continue
            try:
                dim_claims = strategy.evaluate(asset_id, profile)
            except Exception:
                # 한 차원 실패가 전체 분석을 막지 않게 격리.
                dim_claims = []
            claims.extend(dim_claims)
        return claims


class NoOpEvaluationOrchestrator(EvaluationOrchestrator):
    """모든 dimension 에 대해 빈 list 반환 — Orchestrator 가 strategies 미주입 시 fallback."""

    def evaluate(
        self,
        asset_id: str,
        profile: "AssetProfile",
        scope_id: str | None = None,
    ) -> list["EvaluationClaim"]:
        return []
