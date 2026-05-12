"""Observability — LLM 호출/에이전트 흐름의 외부 추적.

레이어:
  base.py       — TraceBackend ABC + TraceContext / GenerationContext + trace_scope() contextmanager
  noop_backend  — 비활성 (production default 가 아니라 테스트/CI 기본값)
  stdout_backend — 로컬 디버깅용 JSON 로깅
  langfuse_backend — Langfuse Cloud / 자체 호스팅 연결

호출 코드는 백엔드 구현을 모름 — TraceBackend 인터페이스로만 접근.
미래에 OpenTelemetry / Phoenix 등 다른 백엔드 추가 시 이 인터페이스만 구현하면 됨.

trace_id 는 보통 Orchestrator scope_id 와 동일 (analysis_<uuid>).
배치 DAG 의 경우 dag_run_id 를 trace_id 로 매핑.
"""
from core.shared.infra.observability.base import (
    GenerationContext,
    TraceBackend,
    TraceContext,
    current_trace,
    trace_scope,
)

__all__ = [
    "TraceBackend",
    "TraceContext",
    "GenerationContext",
    "current_trace",
    "trace_scope",
]
