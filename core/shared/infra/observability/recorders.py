"""LLMCallRecorder + UsageMetricsCollector — 자체 DB 에 LLM 호출 / 사용량 영구화.

확장 자리. Langfuse / Phoenix 같은 외부 백엔드 (TraceBackend) 와 별개로
**우리 자체 DB** 에 row 단위로 LLM 호출 metric 을 적재할 곳.

왜 TraceBackend 와 별개인가:
  - TraceBackend = 외부 observability 서비스로 push (가시화/알람 용도)
  - Recorder    = 우리 DB 에 적재 (대시보드 / 회계 / 자체 분석 용도)
  - 둘 다 켜는 게 일반적: Langfuse 로 실시간 가시화 + DB 로 영구 보존

설계:
  TracingLLMClient 가 end_generation 시점에 양쪽 모두 호출.
  현재는 NoOp 구현이라 동작 변경 0 — 추후 SqliteLLMCallRecorder 추가 시
  composition.py 한 곳만 교체.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class LLMCallRecord:
    """LLM 호출 1회분 metric.

    PolicyGate.record() 와 동일한 데이터 + 시간/지연/모델 메타.
    cost_usd 는 core.llm.pricing.estimate_llm_cost_usd() 결과.
    """
    call_id: str
    scope_id: Optional[str]              # analysis_<uuid> | dag_run_<id> | None
    role: str                            # "ontology_tagging" | "exploration.planner" ...
    model: str
    prompt_key: Optional[str] = None     # "exploration.planner" (PromptCatalog key)
    prompt_version_hash: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: Optional[int] = None
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class LLMCallRecorder(ABC):
    """LLM 호출 metric 의 영구 저장 인터페이스."""

    @abstractmethod
    def record(self, call: LLMCallRecord) -> None: ...

    @abstractmethod
    def find_by_scope(self, scope_id: str) -> list[LLMCallRecord]: ...


class NoOpLLMCallRecorder(LLMCallRecorder):
    """기본 — 외부 호출 / DB write 0. 추후 SqliteLLMCallRecorder 로 교체 가능."""

    def record(self, call: LLMCallRecord) -> None:
        return None

    def find_by_scope(self, scope_id: str) -> list[LLMCallRecord]:
        return []


class InMemoryLLMCallRecorder(LLMCallRecorder):
    """테스트 / 디버깅용 — 프로세스 메모리에 누적."""

    def __init__(self) -> None:
        self._calls: list[LLMCallRecord] = []

    def record(self, call: LLMCallRecord) -> None:
        self._calls.append(call)

    def find_by_scope(self, scope_id: str) -> list[LLMCallRecord]:
        return [c for c in self._calls if c.scope_id == scope_id]

    @property
    def all_calls(self) -> list[LLMCallRecord]:
        return list(self._calls)


# ---------------------------------------------------------------------------
# UsageMetricsCollector — 분석 1회 종료 시 PolicyGate snapshot 을 적재
# ---------------------------------------------------------------------------


@dataclass
class UsageSnapshot:
    """분석 1회 (scope) 또는 배치 1회 (dag_run) 의 사용량 집계.

    PolicyGate.cost_used / input_tokens / output_tokens 의 스냅샷.
    """
    scope_id: str
    snapshot_at: datetime
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    metadata: dict = field(default_factory=dict)


class UsageMetricsCollector(ABC):
    """분석 / 배치 종료 시 누적된 사용량 metric 적재."""

    @abstractmethod
    def submit(self, snapshot: UsageSnapshot) -> None: ...

    @abstractmethod
    def get(self, scope_id: str) -> Optional[UsageSnapshot]: ...


class NoOpUsageMetricsCollector(UsageMetricsCollector):
    def submit(self, snapshot: UsageSnapshot) -> None:
        return None

    def get(self, scope_id: str) -> Optional[UsageSnapshot]:
        return None


class InMemoryUsageMetricsCollector(UsageMetricsCollector):
    def __init__(self) -> None:
        self._by_scope: dict[str, UsageSnapshot] = {}

    def submit(self, snapshot: UsageSnapshot) -> None:
        self._by_scope[snapshot.scope_id] = snapshot

    def get(self, scope_id: str) -> Optional[UsageSnapshot]:
        return self._by_scope.get(scope_id)
