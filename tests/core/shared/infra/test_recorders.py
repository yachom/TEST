"""LLMCallRecorder + UsageMetricsCollector placeholder smoke tests."""
from __future__ import annotations

from datetime import datetime

from core.shared.infra.observability.recorders import (
    InMemoryLLMCallRecorder,
    InMemoryUsageMetricsCollector,
    LLMCallRecord,
    NoOpLLMCallRecorder,
    NoOpUsageMetricsCollector,
    UsageSnapshot,
)


def _make_call(scope_id="s1") -> LLMCallRecord:
    return LLMCallRecord(
        call_id="c1", scope_id=scope_id,
        role="ontology_tagging", model="stub",
        input_tokens=10, output_tokens=5, cost_usd=0.001,
    )


def test_noop_llm_recorder_is_silent():
    r = NoOpLLMCallRecorder()
    r.record(_make_call())
    assert r.find_by_scope("s1") == []


def test_in_memory_llm_recorder_accumulates():
    r = InMemoryLLMCallRecorder()
    r.record(_make_call("s1"))
    r.record(LLMCallRecord(
        call_id="c2", scope_id="s1", role="r", model="m",
        input_tokens=0, output_tokens=0, cost_usd=0.0,
    ))
    r.record(LLMCallRecord(
        call_id="c3", scope_id="s2", role="r", model="m",
        input_tokens=0, output_tokens=0, cost_usd=0.0,
    ))
    assert len(r.find_by_scope("s1")) == 2
    assert len(r.find_by_scope("s2")) == 1
    assert len(r.all_calls) == 3


def test_noop_usage_collector_is_silent():
    c = NoOpUsageMetricsCollector()
    c.submit(UsageSnapshot(scope_id="s1", snapshot_at=datetime.utcnow()))
    assert c.get("s1") is None


def test_in_memory_usage_collector_persists():
    c = InMemoryUsageMetricsCollector()
    snap = UsageSnapshot(
        scope_id="s1", snapshot_at=datetime.utcnow(),
        total_cost_usd=0.01, total_input_tokens=100,
    )
    c.submit(snap)
    fetched = c.get("s1")
    assert fetched is not None
    assert fetched.total_cost_usd == 0.01
