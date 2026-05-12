"""상가형 부동산 — 건물(PNU 기반) 평가 대상."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from core.evaluation.sentiment.target_base import SentimentTarget


@dataclass(frozen=True)
class BuildingTarget(SentimentTarget):
    """건물 단위 평가 대상. PNU(19자리 토지고유번호)로 식별한다."""

    target_type: ClassVar[str] = "building"

    pnu: str            # 토지고유번호 19자리
    address: str = ""   # 사람이 읽을 수 있는 주소 (표시용)

    def unique_key(self) -> str:
        return f"building:{self.pnu}"

    def label(self) -> str:
        return self.address or f"PNU:{self.pnu}"
