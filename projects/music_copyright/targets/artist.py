"""음악 저작권 — 아티스트 평가 대상."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from core.evaluation.sentiment.target_base import SentimentTarget


@dataclass(frozen=True)
class ArtistTarget(SentimentTarget):
    """아티스트 단위 평가 대상. 아티스트명+소속사 조합으로 식별한다."""

    target_type: ClassVar[str] = "artist"

    artist_name: str
    agency: str = ""

    def unique_key(self) -> str:
        return f"artist:{self.artist_name}:{self.agency}"

    def label(self) -> str:
        if self.agency:
            return f"{self.artist_name} ({self.agency})"
        return self.artist_name
