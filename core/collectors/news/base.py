"""뉴스 수집 Provider 추상 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.collectors.news.models import SearchQuery


class NewsSearchProvider(ABC):
    """외부 뉴스 검색 Provider 추상 인터페이스."""

    @abstractmethod
    def search(self, query: SearchQuery) -> list[dict]:
        """검색 실행 후 Provider 원본 응답 목록 반환."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...

    def supports(self, provider_key: str) -> bool:
        return self.provider_name() == provider_key
