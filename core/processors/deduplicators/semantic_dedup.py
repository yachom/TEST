from __future__ import annotations

from typing import TYPE_CHECKING

from core.collectors.news.models import DedupResult
from core.shared.domain.states import DedupStatus

if TYPE_CHECKING:
    from core.collectors.news.repositories.news_repository import NewsRepository
    from core.collectors.news.repositories.embedding_repository import EmbeddingRepository


class SemanticDeduplicationService:
    """임베딩 유사도 기반으로 의미상 중복 뉴스를 판단한다."""

    def __init__(
        self,
        news_repository: "NewsRepository",
        embedding_repository: "EmbeddingRepository",
        similarity_threshold: float = 0.92,
    ) -> None:
        self._news_repo = news_repository
        self._embed_repo = embedding_repository
        self._threshold = similarity_threshold

    def run_batch(self) -> list[DedupResult]:
        pending = self._news_repo.find_pending_dedup()
        results = []
        for article in pending:
            result = self._evaluate(article)
            self._news_repo.update_dedup_status(result)
            results.append(result)
        return results

    def _evaluate(self, article) -> DedupResult:
        vector = self._embed_repo.get_vector(article.id)
        if vector is None:
            return DedupResult(article_id=article.id, is_novel=True)

        similar = self._embed_repo.find_similar(vector, threshold=self._threshold, exclude_id=article.id)
        if similar:
            ref_id, sim_score = similar[0]
            return DedupResult(article_id=article.id, is_novel=False, reference_id=ref_id, similarity=sim_score)

        return DedupResult(article_id=article.id, is_novel=True)
