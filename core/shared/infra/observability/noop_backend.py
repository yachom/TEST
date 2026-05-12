"""NoOpBackend — observability 비활성화 (테스트/CI/Key 누락 시 fallback)."""
from __future__ import annotations

from typing import Any

from core.shared.infra.observability.base import (
    GenerationContext,
    TraceBackend,
    TraceContext,
)


class NoOpBackend(TraceBackend):
    """모든 메서드가 빈 컨텍스트만 반환. 외부 호출 0."""

    def start_trace(
        self,
        name: str,
        trace_id: str,
        metadata: dict | None = None,
    ) -> TraceContext:
        return TraceContext(trace_id=trace_id, name=name, metadata=metadata or {})

    def end_trace(self, ctx: TraceContext, output: Any = None, error: str | None = None) -> None:
        return None

    def start_generation(
        self,
        trace: TraceContext,
        name: str,
        role: str,
        model: str,
        input: dict,
        metadata: dict | None = None,
    ) -> GenerationContext:
        return GenerationContext(
            trace=trace,
            name=name,
            role=role,
            model=model,
            input=input,
            metadata=metadata or {},
        )

    def end_generation(
        self,
        gen: GenerationContext,
        output: str | None = None,
        usage: dict | None = None,
        error: str | None = None,
    ) -> None:
        return None
