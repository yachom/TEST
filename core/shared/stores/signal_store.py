from abc import ABC, abstractmethod
from typing import Optional


class SignalStore(ABC):
    """Market & Policy Signal 저장소.

    배치 파이프라인이 쓰고(upsert),
    On-demand 감성평가가 읽는다(query).
    두 흐름을 연결하는 핵심 브릿지.
    """

    @abstractmethod
    def upsert(self, signal: dict) -> str:
        """신호 저장 또는 갱신. 레코드 ID 반환."""
        ...

    @abstractmethod
    def get(self, signal_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def query_by_asset(self, asset_class: str, limit: int = 50) -> list[dict]:
        ...

    @abstractmethod
    def query_by_region(self, region_code: str, limit: int = 50) -> list[dict]:
        ...

    @abstractmethod
    def query_by_signal_type(self, signal_type: str, limit: int = 50) -> list[dict]:
        ...

    @abstractmethod
    def query_applicable(
        self,
        asset_class: str,
        region_code: Optional[str] = None,
    ) -> list[dict]:
        """On-demand 감성평가 시 해당 자산에 적용 가능한 신호만 반환.

        Applicability.DIRECT 와 NEEDS_VERIFICATION 만 포함.
        BACKGROUND_ONLY 는 별도 조회.
        """
        ...
