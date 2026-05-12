"""TraceBackend ABC + contextvars 기반 trace 전파.

설계:
- 호출 코드는 백엔드 종류를 모름 → TraceBackend 한 인터페이스만 사용.
- trace 는 contextvars 로 자동 전파 → Orchestrator 한 군데서만 trace_scope() 열면
  내부의 모든 LLM 호출이 자동으로 같은 trace 에 속함.
- 백엔드 실패는 silently swallow — observability 가 본 흐름을 망가뜨리지 않음.

라이프사이클:
    with trace_scope(backend, name="address_analysis", trace_id=scope_id) as ctx:
        # 이 블록 안의 모든 TracingLLMClient.call() 이 ctx 에 자동 첨부됨.
        ...

종료 시 backend.end_trace() 가 호출되고 contextvar 가 reset.
예외 발생 시 error 로 종료된 trace 가 기록됨.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator


_log = logging.getLogger(__name__)


@dataclass
class TraceContext:
    """한 분석 단위 (Orchestrator.analyze 한 번, 배치 DAG 1 run 등)."""
    trace_id: str
    name: str
    metadata: dict = field(default_factory=dict)
    backend_handle: Any = None  # 백엔드 객체 (Langfuse Trace, OTEL Span 등)


@dataclass
class GenerationContext:
    """trace 안의 LLM 호출 1건."""
    trace: TraceContext
    name: str
    role: str            # ontology_tagging | exploration.planner | qa.synthesizer ...
    model: str
    input: dict          # {system, user, ...}
    metadata: dict = field(default_factory=dict)
    backend_handle: Any = None


class TraceBackend(ABC):
    """모든 observability 백엔드의 공통 인터페이스.

    예외 안전:
      구현체는 가능한 모든 외부 호출 실패를 catch + log 후 None/no-op 으로 처리.
      observability 가 본 흐름을 깨트리면 안 됨.
    """

    @abstractmethod
    def start_trace(
        self,
        name: str,
        trace_id: str,
        metadata: dict | None = None,
    ) -> TraceContext: ...

    @abstractmethod
    def end_trace(
        self,
        ctx: TraceContext,
        output: Any = None,
        error: str | None = None,
    ) -> None: ...

    @abstractmethod
    def start_generation(
        self,
        trace: TraceContext,
        name: str,
        role: str,
        model: str,
        input: dict,
        metadata: dict | None = None,
    ) -> GenerationContext: ...

    @abstractmethod
    def end_generation(
        self,
        gen: GenerationContext,
        output: str | None = None,
        usage: dict | None = None,
        error: str | None = None,
    ) -> None: ...

    def flush(self) -> None:
        """비동기 background 전송 강제 flush. 기본은 no-op."""
        return None


# ---------------------------------------------------------------------------
# contextvars 기반 현재 trace 전파
# ---------------------------------------------------------------------------

_current_trace: ContextVar[TraceContext | None] = ContextVar(
    "fnpricing_current_trace", default=None
)


def current_trace() -> TraceContext | None:
    """현재 스레드/태스크 가 속한 trace. 없으면 None."""
    return _current_trace.get()


@contextmanager
def trace_scope(
    backend: TraceBackend,
    name: str,
    trace_id: str,
    metadata: dict | None = None,
) -> Iterator[TraceContext]:
    """trace 라이프사이클 컨텍스트 매니저.

    Orchestrator.analyze / 배치 DAG task 진입점에서 한 번만 호출.
    내부에서 일어나는 모든 TracingLLMClient.call() 이 이 trace 에 자동 첨부.
    """
    ctx: TraceContext | None = None
    token = None
    try:
        ctx = backend.start_trace(name, trace_id, metadata or {})
    except Exception as e:  # noqa: BLE001
        _log.warning("trace_scope: start_trace failed (backend=%s): %s", type(backend).__name__, e)
        # 백엔드 실패해도 흐름은 진행 — dummy ctx 로 진행
        ctx = TraceContext(trace_id=trace_id, name=name, metadata=metadata or {})

    token = _current_trace.set(ctx)
    error_msg: str | None = None
    try:
        yield ctx
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        try:
            backend.end_trace(ctx, error=error_msg)
        except Exception as e:  # noqa: BLE001
            _log.warning("trace_scope: end_trace failed: %s", e)
        _current_trace.reset(token)
