"""감정평가 대상 추상 기반 클래스.

자산별 구체 클래스가 이 클래스를 상속한다.
"""
from __future__ import annotations

from core.shared.domain.evaluation import EvaluationTarget


class SentimentTarget(EvaluationTarget):
    """감정평가 대상의 추상 기반.

    자산별 구체 클래스:
      - projects/commercial_real_estate/targets/building.py → BuildingTarget
      - projects/commercial_real_estate/targets/tenant.py  → TenantTarget
      - projects/music_copyright/targets/artist.py         → ArtistTarget
      - projects/music_copyright/targets/song.py           → SongTarget
    """
