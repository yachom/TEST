from abc import ABC, abstractmethod
from typing import Optional


class ReportStore(ABC):
    """감성평가 보고서 패키지 저장소 (On-demand용)."""

    @abstractmethod
    def save(self, address_key: str, report_package: dict) -> str:
        ...

    @abstractmethod
    def get(self, report_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def find_latest_by_address(self, address_key: str) -> Optional[dict]:
        ...
