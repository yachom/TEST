"""Collector 공통 추상화.

모든 외부 데이터 수집 컴포넌트가 구현하는 공통 인터페이스.
소스별 구체 구현은 core/collectors/<source>/ 에 둔다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.shared.domain.asset import AssetClass


@dataclass
class CollectionQuery:
    """단일 수집 요청."""
    text: str
    source_type: str                       # "news", "transaction", "streaming", ...
    asset_class: Optional[AssetClass] = None
    max_results: int = 10
    extra: dict = field(default_factory=dict)  # source별 추가 파라미터


@dataclass
class RawRecord:
    """수집된 원본 레코드 — 얇은 공통 모델.

    세부 데이터 구조는 source_type별 typed accessor가 처리한다.
    content 는 provider 원본 응답을 정규화한 dict.
    """
    source_type: str
    source_id: str                         # provider 내 고유 ID
    content: dict                          # 정규화된 원본
    collected_at: datetime
    metadata: dict = field(default_factory=dict)


@dataclass
class CollectionPlan:
    """수집 실행 계획 — API 호출량 산정 포함."""
    queries: list[CollectionQuery]
    estimated_calls: int
    provider_breakdown: dict[str, int]     # provider → 예상 호출 수


class Collector(ABC):
    """외부 데이터를 수집하는 모든 컴포넌트의 공통 인터페이스.

    구현체 예시: NaverNewsCollector, TransactionCollector, StreamingStatCollector
    """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """이 Collector가 생산하는 source_type 식별자."""

    @abstractmethod
    def collect(self, query: CollectionQuery) -> list[RawRecord]:
        """수집 실행 후 RawRecord 목록 반환."""

    @abstractmethod
    def quota_estimate(self, query: CollectionQuery) -> int:
        """이 쿼리 1회에 소비되는 API 호출 수 추정치."""
