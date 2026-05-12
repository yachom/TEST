"""평가 도메인 핵심 추상화.

EvaluationTarget / EvaluationClaim / AssetProfile 은 자산 무관 공통 모델.
자산별 구체 클래스는 projects/<자산>/targets/ 에 정의한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Optional


# ---------------------------------------------------------------------------
# 평가 축
# ---------------------------------------------------------------------------

class EvaluationDimension(str, Enum):
    QUANTITATIVE = "quantitative"
    STRUCTURAL = "structural"
    SENTIMENT = "sentiment"


# ---------------------------------------------------------------------------
# 평가 대상 (추상)
# ---------------------------------------------------------------------------

class EvaluationTarget(ABC):
    """모든 자산의 평가 대상이 구현해야 하는 공통 인터페이스.

    자산별 구체 클래스:
      - projects/commercial_real_estate/targets/building.py → BuildingTarget
      - projects/commercial_real_estate/targets/tenant.py  → TenantTarget
      - projects/music_copyright/targets/artist.py         → ArtistTarget
      - projects/music_copyright/targets/song.py           → SongTarget
    """

    target_type: ClassVar[str]  # "building", "tenant", "artist", "song", ...

    @abstractmethod
    def unique_key(self) -> str:
        """법적 고유번호 기반 키. PNU, 사업자번호, ISRC, 법인번호 등."""

    @abstractmethod
    def label(self) -> str:
        """사람이 읽을 수 있는 표시명."""


# ---------------------------------------------------------------------------
# 평가 결과 모델
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    """평가 claim 의 근거."""
    source_type: str          # "news", "review", "transaction"
    source_id: str
    excerpt: str
    score_contribution: Optional[float] = None


@dataclass
class EvaluationClaim:
    """평가 3축 × 자산 × 대상의 모든 조합을 표현하는 통합 결과 모델.

    예시 조합:
      - quantitative × 부동산 건물
      - sentiment     × 입점업체
      - structural    × 발행사
    """
    asset_id: str
    target: EvaluationTarget
    dimension: EvaluationDimension
    score: float                       # 0.0 ~ 100.0
    evidence: list[Evidence]
    rationale: str
    created_at: datetime
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 자산 프로파일
# ---------------------------------------------------------------------------

@dataclass
class AssetProfile:
    """자산-평가축-수집소스-검색어그룹 매핑.

    자산 추가 = projects/<자산>/profile.py 에 AssetProfile 인스턴스 1개 정의.
    core/ 수정은 불필요하다.
    """
    asset_class: "AssetClass"                          # noqa: F821
    evaluation_dimensions: list[EvaluationDimension]
    sentiment_target_types: list[type[EvaluationTarget]]
    collector_source_types: list[str]                  # ["news", "streaming", ...]
    config_path: Path                                  # search_groups.yaml 경로
    ontology_schema_module: str                        # 자산 특화 평가 요인 사전 모듈

    def root_dir(self) -> Path:
        return self.config_path.parent.parent
