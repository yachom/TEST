from abc import ABC, abstractmethod
from typing import Optional


class OntologyStore(ABC):
    """1차 온톨로지 매핑 결과 저장소."""

    @abstractmethod
    def save(self, record: dict) -> str:
        ...

    @abstractmethod
    def get(self, record_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def find_by_source_record(self, source: str, source_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def find_by_asset_class(self, asset_class: str, limit: int = 100) -> list[dict]:
        ...
