"""음악 저작권 — 음원(ISRC 기반) 평가 대상."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from core.evaluation.sentiment.target_base import SentimentTarget


@dataclass(frozen=True)
class SongTarget(SentimentTarget):
    """음원 단위 평가 대상. ISRC(12자리 국제표준음반코드)로 식별한다."""

    target_type: ClassVar[str] = "song"

    isrc: str           # 국제표준음반코드 12자리
    title: str = ""     # 곡명 (표시용)
    artist: str = ""    # 아티스트명 (표시용)

    def unique_key(self) -> str:
        return f"song:{self.isrc}"

    def label(self) -> str:
        parts = [p for p in [self.title, self.artist] if p]
        return " - ".join(parts) if parts else f"ISRC:{self.isrc}"
