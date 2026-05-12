from __future__ import annotations

from typing import Optional

from core.collectors.news.models import FilterResult, DedupResult, TaggingResult, NewsArticle
from core.collectors.news.repositories.news_repository import NewsRepository
from core.shared.domain.states import (
    FilterStatus,
    EmbeddingStatus,
    DedupStatus,
    TagStatus,
    GraphStatus,
    GraphExcludeReason,
)


class InMemoryNewsRepository(NewsRepository):
    """테스트 및 초기 개발용 인메모리 구현체."""

    def __init__(self) -> None:
        self._by_id: dict[str, NewsArticle] = {}
        self._url_index: set[str] = set()
        self._hash_index: set[str] = set()

    def save(self, article: NewsArticle) -> None:
        self._by_id[article.id] = article
        self._url_index.add(article.normalized_url)
        self._hash_index.add(article.content_hash)

    def exists_by_url(self, normalized_url: str) -> bool:
        return normalized_url in self._url_index

    def exists_by_hash(self, content_hash: str) -> bool:
        return content_hash in self._hash_index

    def get(self, article_id: str) -> Optional[NewsArticle]:
        return self._by_id.get(article_id)

    def find_pending_filter(self) -> list[NewsArticle]:
        return [a for a in self._by_id.values() if a.filter_status == FilterStatus.PENDING]

    def find_pending_embed(self) -> list[NewsArticle]:
        return [
            a for a in self._by_id.values()
            if a.filter_status == FilterStatus.PASSED and a.embedding_status == EmbeddingStatus.PENDING
        ]

    def find_pending_dedup(self) -> list[NewsArticle]:
        return [
            a for a in self._by_id.values()
            if a.embedding_status == EmbeddingStatus.DONE and a.dedup_status == DedupStatus.PENDING
        ]

    def find_pending_tag(self) -> list[NewsArticle]:
        return [
            a for a in self._by_id.values()
            if a.dedup_status == DedupStatus.NOVEL and a.tag_status == TagStatus.PENDING
        ]

    def find_pending_graph(self) -> list[NewsArticle]:
        return [
            a for a in self._by_id.values()
            if a.tag_status == TagStatus.DONE and a.graph_status == GraphStatus.PENDING
        ]

    def update_filter_status(self, result: FilterResult) -> None:
        article = self._by_id.get(result.article_id)
        if article is None:
            return
        article.filter_status = FilterStatus.PASSED if result.passed else FilterStatus.EXCLUDED
        article.filter_exclude_reason = result.exclude_reason

    def update_embedding_status(self, article_id: str, status: EmbeddingStatus) -> None:
        article = self._by_id.get(article_id)
        if article:
            article.embedding_status = status

    def update_dedup_status(self, result: DedupResult) -> None:
        article = self._by_id.get(result.article_id)
        if article is None:
            return
        article.dedup_status = DedupStatus.NOVEL if result.is_novel else DedupStatus.DUPLICATE
        article.dedup_reference_id = result.reference_id

    def update_tag_status(self, article_id: str, result: TaggingResult) -> None:
        article = self._by_id.get(article_id)
        if article is None:
            return
        article.tag_status = TagStatus.DONE if result.success else TagStatus.FAILED
        article.tag_exclude_reason = result.exclude_reason

    def update_graph_status(
        self,
        article_id: str,
        status: GraphStatus,
        reason: Optional[GraphExcludeReason] = None,
    ) -> None:
        article = self._by_id.get(article_id)
        if article is None:
            return
        article.graph_status = status
        article.graph_exclude_reason = reason

    def all(self) -> list[NewsArticle]:
        return list(self._by_id.values())

    def count(self) -> int:
        return len(self._by_id)
