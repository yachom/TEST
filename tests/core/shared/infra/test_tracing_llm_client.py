"""TracingLLMClient + trace_scope + observability backend 통합 동작 검증.

테스트 패턴:
- _RecordingBackend 가 모든 콜백을 list 로 저장 → 호출 시퀀스 / payload 검증.
- StubLLMClient 가 빈 응답을 주므로 LLM 자체 호출은 deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.agents.policy import AgentPolicy, PolicyGate
from core.shared.infra.llm_client import LLMRequest, StubLLMClient
from core.shared.infra.observability.base import (
    GenerationContext,
    TraceBackend,
    TraceContext,
    current_trace,
    trace_scope,
)
from core.shared.infra.tracing_llm_client import TracingLLMClient


@dataclass
class _Event:
    kind: str
    payload: dict


class _RecordingBackend(TraceBackend):
    def __init__(self) -> None:
        self.events: list[_Event] = []

    def start_trace(self, name, trace_id, metadata=None):
        ctx = TraceContext(trace_id=trace_id, name=name, metadata=metadata or {})
        self.events.append(_Event("trace.start", {"name": name, "trace_id": trace_id}))
        return ctx

    def end_trace(self, ctx, output=None, error=None):
        self.events.append(_Event("trace.end", {"trace_id": ctx.trace_id, "error": error}))

    def start_generation(self, trace, name, role, model, input, metadata=None):
        gen = GenerationContext(
            trace=trace, name=name, role=role, model=model, input=input,
            metadata=metadata or {},
        )
        self.events.append(_Event("generation.start", {"name": name, "role": role, "model": model}))
        return gen

    def end_generation(self, gen, output=None, usage=None, error=None):
        self.events.append(_Event("generation.end", {
            "role": gen.role,
            "output": output,
            "usage": usage,
            "error": error,
        }))


def _new_request() -> LLMRequest:
    return LLMRequest(
        system_prompt="sys",
        user_prompt="usr",
        response_schema={"type": "object"},
    )


def test_tracing_client_no_op_outside_trace_scope():
    backend = _RecordingBackend()
    client = TracingLLMClient(StubLLMClient(), backend, role="test")

    # trace_scope 밖에서 호출 → backend 이벤트 없음
    resp = client.call(_new_request())
    assert resp.content == "{}"
    assert backend.events == []


def test_tracing_client_emits_generation_inside_trace_scope():
    backend = _RecordingBackend()
    client = TracingLLMClient(StubLLMClient(), backend, role="ontology_tagging")

    with trace_scope(backend, name="address_analysis", trace_id="trace_x") as ctx:
        assert current_trace() is ctx
        client.call(_new_request())
        client.call(_new_request())

    # 시퀀스: trace.start → gen.start → gen.end → gen.start → gen.end → trace.end
    kinds = [e.kind for e in backend.events]
    assert kinds == [
        "trace.start",
        "generation.start", "generation.end",
        "generation.start", "generation.end",
        "trace.end",
    ]
    # 역할이 generation 으로 전달됨
    assert backend.events[1].payload["role"] == "ontology_tagging"


def test_tracing_client_records_error_then_reraises():
    backend = _RecordingBackend()

    class _BoomClient(StubLLMClient):
        def call(self, request):
            raise RuntimeError("boom")

    client = TracingLLMClient(_BoomClient(), backend, role="r")

    raised = False
    with trace_scope(backend, name="t", trace_id="t1"):
        try:
            client.call(_new_request())
        except RuntimeError:
            raised = True
    assert raised

    end_gen = [e for e in backend.events if e.kind == "generation.end"][0]
    assert end_gen.payload["error"] == "boom"


def test_tracing_client_after_scope_resets_contextvar():
    backend = _RecordingBackend()
    with trace_scope(backend, name="t", trace_id="t1"):
        assert current_trace() is not None
    assert current_trace() is None


def test_policy_gate_auto_records_usage_via_tracing_client():
    backend = _RecordingBackend()

    class _UsageReportingClient(StubLLMClient):
        def call(self, request):
            from core.shared.infra.llm_client import LLMResponse
            return LLMResponse(
                content="{}", parsed={}, model="stub",
                usage={"input_tokens": 100, "output_tokens": 50},
            )

    gate = PolicyGate(AgentPolicy(max_tool_calls=10, max_cost_usd=1.0))
    client = TracingLLMClient(
        _UsageReportingClient(), backend, role="r", policy_gate=gate,
    )

    with trace_scope(backend, "t", "t1"):
        client.call(_new_request())
        client.call(_new_request())

    # call_count 가 2 회 누적, input/output tokens 도 누적
    assert gate.call_count == 2
    assert gate.input_tokens == 200
    assert gate.output_tokens == 100
