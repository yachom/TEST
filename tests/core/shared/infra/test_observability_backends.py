"""NoOp / Stdout / Langfuse backend smoke tests (외부 호출 없이)."""
from __future__ import annotations

import io
import json

from core.shared.infra.observability.langfuse_backend import LangfuseBackend
from core.shared.infra.observability.noop_backend import NoOpBackend
from core.shared.infra.observability.stdout_backend import StdoutBackend


def test_noop_backend_methods_return_dummy_contexts():
    b = NoOpBackend()
    trace = b.start_trace("t", "id1", {"address": "x"})
    assert trace.trace_id == "id1"
    gen = b.start_generation(trace, "g", "role", "model", {"system": "s", "user": "u"})
    assert gen.role == "role"
    # 종료 호출은 그냥 pass
    b.end_generation(gen, output="o", usage={"input_tokens": 1})
    b.end_trace(trace)


def test_stdout_backend_emits_json_lines_without_prompts_by_default():
    buf = io.StringIO()
    b = StdoutBackend(stream=buf, include_prompts=False)

    trace = b.start_trace("addr_analysis", "tr_1", {"address": "강남구"})
    gen = b.start_generation(
        trace, "llm.tagger", "ontology_tagging", "claude-haiku",
        input={"system": "very long " * 100, "user": "u"},
    )
    b.end_generation(gen, output="ok" * 50, usage={"input_tokens": 200, "output_tokens": 80})
    b.end_trace(trace)

    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    events = [json.loads(ln) for ln in lines]
    kinds = [e["event"] for e in events]
    assert kinds == ["trace.start", "generation.start", "generation.end", "trace.end"]
    # prompts 미포함 모드: input/output 자체는 없고 길이만 노출
    gen_start = events[1]
    assert "input" not in gen_start
    assert "input_chars" in gen_start


def test_langfuse_backend_disabled_without_keys_does_not_crash():
    # 키 없이 생성 → 내부적으로 disabled, 호출은 no-op
    b = LangfuseBackend(public_key="", secret_key="")
    trace = b.start_trace("t", "id", {})
    assert trace.backend_handle is None
    gen = b.start_generation(trace, "g", "r", "m", {"system": "s", "user": "u"})
    b.end_generation(gen, output="o", usage={"input_tokens": 1})
    b.end_trace(trace)
    b.flush()
