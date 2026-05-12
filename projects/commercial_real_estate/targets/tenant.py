"""상가형 부동산 — 입점업체(사업자번호 기반) 평가 대상."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from core.evaluation.sentiment.target_base import SentimentTarget


@dataclass(frozen=True)
class TenantTarget(SentimentTarget):
    """입점업체 단위 평가 대상. 사업자등록번호(10자리)로 식별한다."""

    target_type: ClassVar[str] = "tenant"

    business_number: str    # 사업자등록번호 10자리
    business_name: str = "" # 상호 (표시용)

    def unique_key(self) -> str:
        return f"tenant:{self.business_number}"

    def label(self) -> str:
        return self.business_name or f"사업자:{self.business_number}"
