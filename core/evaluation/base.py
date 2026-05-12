"""평가 전략 공통 추상화.

평가 3축(정량/구조/감정)이 모두 구현해야 하는 인터페이스.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from core.shared.domain.evaluation import EvaluationClaim, EvaluationDimension

if TYPE_CHECKING:
    from core.shared.domain.evaluation import AssetProfile


class EvaluationStrategy(ABC):
    """평가 3축 공통 추상 인터페이스.

    구현체:
      - SentimentEvaluationStrategy  (본 구현)
      - QuantitativeEvaluationStrategy (stub)
      - StructuralEvaluationStrategy   (stub)
    """

    @property
    @abstractmethod
    def dimension(self) -> EvaluationDimension:
        """이 전략이 담당하는 평가 축."""

    @abstractmethod
    def evaluate(
        self,
        asset_id: str,
        profile: "AssetProfile",
    ) -> list[EvaluationClaim]:
        """평가를 수행하고 EvaluationClaim 목록을 반환한다."""
