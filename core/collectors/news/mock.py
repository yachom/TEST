from __future__ import annotations

from datetime import datetime, timezone

from core.collectors.news.models import SearchQuery
from core.collectors.news.base import NewsSearchProvider


class MockNewsSearchProvider(NewsSearchProvider):
    """테스트 및 로컬 개발용 Provider — 결정적 가짜 뉴스 응답을 반환한다."""

    def __init__(self, items_per_query: int = 3) -> None:
        self._items = items_per_query

    def search(self, query: SearchQuery) -> list[dict]:
        pub = datetime.now(tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0900")
        return [
            {
                "title": f"[Mock] {query.text} 관련 뉴스 {i + 1}",
                "description": f"{query.text} 시장 동향 — 테스트용 기사 {i + 1}.",
                "originallink": f"https://mock.news/article/{hash(query.text) % 9999}/{i}",
                "link": f"https://n.news.naver.com/article/mock/{i}",
                "pubDate": pub,
            }
            for i in range(self._items)
        ]

    def provider_name(self) -> str:
        return "naver"
