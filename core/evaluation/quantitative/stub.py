"""정량 평가 Stub — 인터페이스만 정의, 실제 계산 미구현."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from core.evaluation.base import EvaluationStrategy
from core.shared.domain.evaluation import EvaluationClaim, EvaluationDimension

if TYPE_CHECKING:
    from core.shared.domain.evaluation import AssetProfile


class QuantitativeEvaluationStrategy(EvaluationStrategy):
    """정량 평가 Stub. DCF / NOI / Cap Rate 등은 추후 구현."""

    @property
    def dimension(self) -> EvaluationDimension:
        return EvaluationDimension.QUANTITATIVE

    def evaluate(self, asset_id: str, profile: "AssetProfile") -> list[EvaluationClaim]:
        # TODO: 실제 정량 계산 구현
        return []
