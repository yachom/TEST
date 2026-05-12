"""감정평가 Claim 빌더 — 신호 목록에서 EvaluationClaim 을 생성한다."""
from __future__ import annotations

from datetime import datetime

from core.shared.domain.evaluation import EvaluationClaim, EvaluationDimension, Evidence, EvaluationTarget


class SentimentClaimBuilder:
    """신호 목록 + 평가 대상 → EvaluationClaim.

    점수 산출 방식은 추후 확정 후 채운다 (POC 이후).
    """

    def build(
        self,
        asset_id: str,
        target: EvaluationTarget,
        signals: list[dict],
    ) -> EvaluationClaim:
        evidence = [
            Evidence(
                source_type=s.get("source_type", "news"),
                source_id=s.get("article_id", ""),
                excerpt=s.get("summary", ""),
                score_contribution=None,
            )
            for s in signals
        ]
        score = self._compute_score(signals)
        return EvaluationClaim(
            asset_id=asset_id,
            target=target,
            dimension=EvaluationDimension.SENTIMENT,
            score=score,
            evidence=evidence,
            rationale=self._build_rationale(signals),
            created_at=datetime.utcnow(),
        )

    @staticmethod
    def _compute_score(signals: list[dict]) -> float:
        """TODO: 실제 점수 산출 구현. 현재는 0.0 반환."""
        return 0.0

    @staticmethod
    def _build_rationale(signals: list[dict]) -> str:
        if not signals:
            return "적용 가능한 신호 없음."
        summaries = [s.get("summary", "") for s in signals[:3] if s.get("summary")]
        return " / ".join(summaries) or "신호 요약 없음."
