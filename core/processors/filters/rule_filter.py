from __future__ import annotations

from typing import TYPE_CHECKING

from core.collectors.news.models import FilterResult, NewsArticle
from core.shared.domain.states import FilterExcludeReason

if TYPE_CHECKING:
    from core.collectors.news.repositories.news_repository import NewsRepository


_AD_KEYWORDS = frozenset(["광고", "PR", "sponsored", "협찬", "제공", "분양 홍보"])


class RuleFilterService:
    """뉴스가 후속 처리 대상인지 1차 판단하는 룰 기반 필터."""

    def __init__(
        self,
        repository: "NewsRepository",
        signal_keywords: list[str],
        asset_keywords: list[str],
        min_text_length: int = 10,
    ) -> None:
        self._repository = repository
        self._signal_kw = frozenset(signal_keywords)
        self._asset_kw = frozenset(asset_keywords)
        self._min_len = min_text_length

    def run_batch(self) -> list[FilterResult]:
        pending = self._repository.find_pending_filter()
        results = [self._evaluate(a) for a in pending]
        for result in results:
            self._repository.update_filter_status(result)
        return results

    def evaluate(self, article: NewsArticle) -> FilterResult:
        return self._evaluate(article)

    def _evaluate(self, article: NewsArticle) -> FilterResult:
        text = f"{article.title} {article.description}"

        if len(text.strip()) < self._min_len:
            return FilterResult(article_id=article.id, passed=False, exclude_reason=FilterExcludeReason.INSUFFICIENT_TEXT)

        if any(kw in text for kw in _AD_KEYWORDS):
            return FilterResult(article_id=article.id, passed=False, exclude_reason=FilterExcludeReason.ADVERTISEMENT)

        has_asset = any(kw in text for kw in self._asset_kw)
        has_signal = any(kw in text for kw in self._signal_kw)

        if not has_asset:
            return FilterResult(article_id=article.id, passed=False, exclude_reason=FilterExcludeReason.IRRELEVANT_ASSET)

        if not has_signal:
            return FilterResult(article_id=article.id, passed=False, exclude_reason=FilterExcludeReason.NO_SIGNAL_KEYWORD)

        return FilterResult(article_id=article.id, passed=True)
