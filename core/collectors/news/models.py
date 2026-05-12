"""뉴스 수집 도메인 모델.

검색 설정(SearchGroup/Query/Plan)과 수집 결과(NewsArticle, 각종 Result)를 정의한다.
OntologyTag 및 MarketSignalCandidate는 taggers/models.py 에 위치한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.shared.domain.asset import AssetFamily, AssetClass
from core.shared.domain.states import (
    IngestionStatus,
    FilterStatus,
    FilterExcludeReason,
    EmbeddingStatus,
    DedupStatus,
    TagStatus,
    TagExcludeReason,
    GraphStatus,
    GraphExcludeReason,
)


# ---------------------------------------------------------------------------
# 검색 설정
# ---------------------------------------------------------------------------

@dataclass
class SearchQuery:
    text: str
    group_name: str
    provider: str
    asset_family: Optional[AssetFamily] = None
    asset_class: Optional[AssetClass] = None
    max_display: int = 10
    max_pages: int = 1
    sort: str = "date"
    active: bool = True


@dataclass
class SearchGroup:
    name: str
    active: bool
    priority: int
    schedule_type: str
    provider: str
    queries: list[SearchQuery]
    asset_family: Optional[AssetFamily] = None
    asset_class: Optional[AssetClass] = None
    max_display: int = 10
    max_pages: int = 1
    sort: str = "date"
    post_process: bool = True
    enable_llm_tagging: bool = True


@dataclass
class SearchPlan:
    groups: list[SearchGroup]
    queries: list[SearchQuery]
    estimated_calls: int
    provider_breakdown: dict[str, int] = field(default_factory=dict)

    @property
    def total_queries(self) -> int:
        return len(self.queries)


# ---------------------------------------------------------------------------
# 뉴스 기사
# ---------------------------------------------------------------------------

@dataclass
class NewsArticle:
    id: str
    title: str
    description: str
    original_link: str
    provider_link: str
    pub_date: Optional[datetime]
    collected_at: datetime
    search_query: str
    search_group: str
    provider: str
    normalized_url: str
    content_hash: str
    asset_family: Optional[AssetFamily] = None
    asset_class: Optional[AssetClass] = None
    raw_response: Optional[dict] = None

    ingestion_status: IngestionStatus = IngestionStatus.NEW
    filter_status: FilterStatus = FilterStatus.PENDING
    filter_exclude_reason: Optional[FilterExcludeReason] = None
    embedding_status: EmbeddingStatus = EmbeddingStatus.PENDING
    dedup_status: DedupStatus = DedupStatus.PENDING
    dedup_reference_id: Optional[str] = None
    tag_status: TagStatus = TagStatus.PENDING
    tag_exclude_reason: Optional[TagExcludeReason] = None
    graph_status: GraphStatus = GraphStatus.PENDING
    graph_exclude_reason: Optional[GraphExcludeReason] = None


# ---------------------------------------------------------------------------
# 서비스 결과 객체
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    article_id: str
    passed: bool
    exclude_reason: Optional[FilterExcludeReason] = None


@dataclass
class ArticleEmbeddingResult:
    article_id: str
    vector: list[float]
    model: str
    success: bool
    error: Optional[str] = None


@dataclass
class DedupResult:
    article_id: str
    is_novel: bool
    reference_id: Optional[str] = None
    similarity: Optional[float] = None


@dataclass
class TaggingResult:
    article_id: str
    success: bool
    tag: Optional["OntologyTag"] = None  # noqa: F821
    exclude_reason: Optional[TagExcludeReason] = None
    error: Optional[str] = None


@dataclass
class SearchRunResult:
    total_fetched: int
    new_saved: int
    url_duplicates: int
    hash_duplicates: int
    save_failures: int
    provider: str
    query_count: int
    elapsed_seconds: float
