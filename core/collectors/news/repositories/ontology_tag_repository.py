from abc import ABC, abstractmethod
from typing import Optional

from core.processors.taggers.models import OntologyTag


class OntologyTagRepository(ABC):
    """LLM 온톨로지 태깅 결과 저장·조회 인터페이스."""

    @abstractmethod
    def save(self, tag: OntologyTag) -> None: ...

    @abstractmethod
    def get(self, article_id: str) -> Optional[OntologyTag]: ...

    @abstractmethod
    def find_pending_graph(self) -> list[OntologyTag]:
        """Graph 적재 대기 중인 태그 목록."""
        ...

    @abstractmethod
    def find_by_asset_class(self, asset_class: str, limit: int = 100) -> list[OntologyTag]: ...

    @abstractmethod
    def mark_graph_done(self, article_id: str) -> None: ...
