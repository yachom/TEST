from abc import ABC, abstractmethod
from typing import Optional


class EmbeddingRepository(ABC):
    """임베딩 벡터 저장·조회·유사도 검색 인터페이스."""

    @abstractmethod
    def save(self, article_id: str, vector: list[float], model: str) -> None: ...

    @abstractmethod
    def get_vector(self, article_id: str) -> Optional[list[float]]: ...

    @abstractmethod
    def find_similar(
        self,
        vector: list[float],
        threshold: float,
        exclude_id: str | None = None,
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        """(article_id, similarity_score) 목록을 내림차순으로 반환."""
        ...
