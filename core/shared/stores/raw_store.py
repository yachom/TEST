from abc import ABC, abstractmethod
from typing import Optional


class RawStore(ABC):
    """원본 수집 데이터 저장소."""

    @abstractmethod
    def save(self, source: str, identifier: str, data: dict, metadata: dict | None = None) -> str:
        ...

    @abstractmethod
    def exists(self, source: str, identifier: str) -> bool:
        ...

    @abstractmethod
    def get(self, record_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def find_by_source(self, source: str, limit: int = 100) -> list[dict]:
        ...

    @abstractmethod
    def find_by_address(self, address_key: str, source: str | None = None) -> list[dict]:
        ...
