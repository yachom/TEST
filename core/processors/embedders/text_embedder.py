from __future__ import annotations

from typing import TYPE_CHECKING

from core.collectors.news.models import ArticleEmbeddingResult
from core.shared.domain.states import EmbeddingStatus

if TYPE_CHECKING:
    from core.collectors.news.repositories.news_repository import NewsRepository
    from core.collectors.news.repositories.embedding_repository import EmbeddingRepository
    from core.shared.infra.embedding_adapter import EmbeddingAdapter


class TextEmbedderService:
    """필터를 통과한 뉴스의 임베딩 벡터를 생성하고 저장한다."""

    def __init__(
        self,
        news_repository: "NewsRepository",
        embedding_repository: "EmbeddingRepository",
        adapter: "EmbeddingAdapter",
    ) -> None:
        self._news_repo = news_repository
        self._embed_repo = embedding_repository
        self._adapter = adapter

    def run_batch(self) -> list[ArticleEmbeddingResult]:
        pending = self._news_repo.find_pending_embed()
        results = []
        for article in pending:
            text = f"{article.title}. {article.description}"
            try:
                raw = self._adapter.embed(text)
                result = ArticleEmbeddingResult(
                    article_id=article.id, vector=raw.vector, model=raw.model, success=True
                )
                self._embed_repo.save(article.id, raw.vector, raw.model)
                self._news_repo.update_embedding_status(article.id, EmbeddingStatus.DONE)
            except Exception as e:
                result = ArticleEmbeddingResult(
                    article_id=article.id, vector=[], model="", success=False, error=str(e)
                )
                self._news_repo.update_embedding_status(article.id, EmbeddingStatus.FAILED)
            results.append(result)
        return results
