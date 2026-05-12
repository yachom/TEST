"""AnalysisRunStore — on-demand 주소 분석 1회 의 메타 영구화 자리.

확장 자리. 현재는 InMemoryAnalysisRunStore 만 — 프로세스 종료 시 휘발.
추후 SqliteAnalysisRunStore / PostgresAnalysisRunStore 추가 시 인터페이스 변경 0.

대시보드 raw 자료의 출발점:
  - 자산/주소별 분석 횟수
  - 시간대별 분석 latency / 비용
  - 분석 결과 (score, summary) 의 시계열 변화
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AnalysisRunRecord:
    """on-demand 분석 1회분 메타.

    AnalysisResult 의 평탄화 + 추적 메트릭 (cost / tokens / latency).
    """
    scope_id: str
    asset_class: str
    address: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    report_summary: str = ""
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> Optional[float]:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class AnalysisRunStore(ABC):
    """on-demand 분석 1회분 메타 저장/조회."""

    @abstractmethod
    def save(self, record: AnalysisRunRecord) -> None: ...

    @abstractmethod
    def get(self, scope_id: str) -> Optional[AnalysisRunRecord]: ...

    @abstractmethod
    def list_recent(self, limit: int = 50) -> list[AnalysisRunRecord]: ...


class InMemoryAnalysisRunStore(AnalysisRunStore):
    """POC 휘발 구현. 프로세스 종료 시 사라짐."""

    def __init__(self) -> None:
        self._by_scope: dict[str, AnalysisRunRecord] = {}

    def save(self, record: AnalysisRunRecord) -> None:
        self._by_scope[record.scope_id] = record

    def get(self, scope_id: str) -> Optional[AnalysisRunRecord]:
        return self._by_scope.get(scope_id)

    def list_recent(self, limit: int = 50) -> list[AnalysisRunRecord]:
        recs = sorted(
            self._by_scope.values(),
            key=lambda r: r.started_at,
            reverse=True,
        )
        return recs[:limit]
