"""감정평가 전략 — 배치 파이프라인이 쌓은 신호를 읽어 claim을 생성한다."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from core.evaluation.base import EvaluationStrategy
from core.shared.domain.evaluation import EvaluationClaim, EvaluationDimension, Evidence

if TYPE_CHECKING:
    from core.shared.domain.evaluation import AssetProfile
    from core.shared.stores.signal_store import SignalStore


class SentimentEvaluationStrategy(EvaluationStrategy):
    """signal_store 에서 적용 가능한 신호를 조회하여 감정평가 claim 을 생성.

    On-demand 단일 자산 분석에서 사용한다.
    """

    def __init__(self, signal_store: "SignalStore") -> None:
        self._signal_store = signal_store

    @property
    def dimension(self) -> EvaluationDimension:
        return EvaluationDimension.SENTIMENT

    def evaluate(self, asset_id: str, profile: "AssetProfile") -> list[EvaluationClaim]:
        """signal_store 에서 applicable 신호를 조회해 target별 claim 을 생성한다.

        TODO: 실제 점수 산출 로직 구현 (score_builder).
        현재는 흐름만 구성한다.
        """
        asset_class_str = profile.asset_class.value
        signals = self._signal_store.query_applicable(asset_class=asset_class_str)

        claims: list[EvaluationClaim] = []
        for target_type in profile.sentiment_target_types:
            # TODO: target별 applicable 신호 필터링 + 점수 산출
            claim = EvaluationClaim(
                asset_id=asset_id,
                target=_StubTarget(target_type.target_type),  # type: ignore
                dimension=EvaluationDimension.SENTIMENT,
                score=0.0,
                evidence=[
                    Evidence(
                        source_type=s.get("source_type", "news"),
                        source_id=s.get("article_id", ""),
                        excerpt=s.get("summary", ""),
                    )
                    for s in signals[:5]
                ],
                rationale="(stub — score builder 미구현)",
                created_at=datetime.utcnow(),
            )
            claims.append(claim)
        return claims


class _StubTarget:
    """strategy.py 내부에서만 사용하는 임시 대상 표현."""
    def __init__(self, target_type: str) -> None:
        self.target_type = target_type

    def unique_key(self) -> str:
        return f"stub:{self.target_type}"

    def label(self) -> str:
        return self.target_type
