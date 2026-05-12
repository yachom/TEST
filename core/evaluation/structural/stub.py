"""구조 평가 Stub — 인터페이스만 정의, 실제 계산 미구현."""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.evaluation.base import EvaluationStrategy
from core.shared.domain.evaluation import EvaluationClaim, EvaluationDimension

if TYPE_CHECKING:
    from core.shared.domain.evaluation import AssetProfile


class StructuralEvaluationStrategy(EvaluationStrategy):
    """구조 평가 Stub. 토큰 구조 / 신탁 구조 평가는 추후 구현."""

    @property
    def dimension(self) -> EvaluationDimension:
        return EvaluationDimension.STRUCTURAL

    def evaluate(self, asset_id: str, profile: "AssetProfile") -> list[EvaluationClaim]:
        # TODO: 실제 구조 평가 구현
        return []
