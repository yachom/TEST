from abc import ABC, abstractmethod
from typing import Optional

from core.collectors.news.models import FilterResult, DedupResult, TaggingResult, NewsArticle
from core.shared.domain.states import EmbeddingStatus, GraphStatus, GraphExcludeReason


class NewsRepository(ABC):
    """뉴스 메타데이터 저장·조회·상태 관리 인터페이스."""

    @abstractmethod
    def save(self, article: NewsArticle) -> None: ...

    @abstractmethod
    def exists_by_url(self, normalized_url: str) -> bool: ...

    @abstractmethod
    def exists_by_hash(self, content_hash: str) -> bool: ...

    @abstractmethod
    def get(self, article_id: str) -> Optional[NewsArticle]: ...

    @abstractmethod
    def find_pending_filter(self) -> list[NewsArticle]: ...

    @abstractmethod
    def find_pending_embed(self) -> list[NewsArticle]: ...

    @abstractmethod
    def find_pending_dedup(self) -> list[NewsArticle]: ...

    @abstractmethod
    def find_pending_tag(self) -> list[NewsArticle]: ...

    @abstractmethod
    def find_pending_graph(self) -> list[NewsArticle]: ...

    @abstractmethod
    def update_filter_status(self, result: FilterResult) -> None: ...

    @abstractmethod
    def update_embedding_status(self, article_id: str, status: EmbeddingStatus) -> None: ...

    @abstractmethod
    def update_dedup_status(self, result: DedupResult) -> None: ...

    @abstractmethod
    def update_tag_status(self, article_id: str, result: TaggingResult) -> None: ...

    @abstractmethod
    def update_graph_status(
        self,
        article_id: str,
        status: GraphStatus,
        reason: Optional[GraphExcludeReason] = None,
    ) -> None: ...
