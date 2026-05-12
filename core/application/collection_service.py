"""뉴스 수집 유스케이스 서비스 — Airflow DAG와 LLM Tool 양쪽에서 호출한다."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.collectors.news.models import SearchPlan, SearchRunResult
from core.shared.domain.states import IngestionStatus

if TYPE_CHECKING:
    from core.collectors.news.base import NewsSearchProvider
    from core.collectors.news.normalizer import NewsNormalizer
    from core.collectors.news.repositories.news_repository import NewsRepository


class NewsSearchApplicationService:
    """뉴스 검색 유스케이스의 중심 서비스.

    save=False 이면 저장 없이 결과만 반환한다 (LLM Tool 조회 전용 모드).
    """

    def __init__(
        self,
        provider_registry: dict[str, "NewsSearchProvider"],
        normalizer: "NewsNormalizer",
        repository: "NewsRepository",
    ) -> None:
        self._providers = provider_registry
        self._normalizer = normalizer
        self._repository = repository

    def execute(self, plan: SearchPlan, save: bool = True) -> SearchRunResult:
        start = time.monotonic()

        total_fetched = 0
        new_saved = 0
        url_duplicates = 0
        hash_duplicates = 0
        save_failures = 0

        for query in plan.queries:
            provider = self._providers.get(query.provider)
            if provider is None:
                continue
            try:
                raw_results = provider.search(query)
            except Exception:
                continue

            for raw in raw_results:
                total_fetched += 1
                article = self._normalizer.normalize(raw, query)

                if not save:
                    continue

                if self._repository.exists_by_url(article.normalized_url):
                    url_duplicates += 1
                    article.ingestion_status = IngestionStatus.URL_DUPLICATE
                    continue

                if self._repository.exists_by_hash(article.content_hash):
                    hash_duplicates += 1
                    article.ingestion_status = IngestionStatus.HASH_DUPLICATE
                    continue

                try:
                    self._repository.save(article)
                    new_saved += 1
                except Exception:
                    save_failures += 1

        elapsed = time.monotonic() - start

        return SearchRunResult(
            total_fetched=total_fetched,
            new_saved=new_saved,
            url_duplicates=url_duplicates,
            hash_duplicates=hash_duplicates,
            save_failures=save_failures,
            provider=",".join(plan.provider_breakdown.keys()),
            query_count=plan.total_queries,
            elapsed_seconds=round(elapsed, 2),
        )
