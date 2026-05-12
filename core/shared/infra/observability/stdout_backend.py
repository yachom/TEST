"""StdoutBackend — 로컬 디버깅용 JSON line 로깅.

각 trace / generation 의 시작·종료를 stdout 또는 stderr 에 출력.
Langfuse 가져오기 전 단계의 가벼운 가시성 확보용.

prompt 입출력은 길어질 수 있으므로 length 만 로그하고, --verbose 필요 시 확장.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, TextIO

from core.shared.infra.observability.base import (
    GenerationContext,
    TraceBackend,
    TraceContext,
)


class StdoutBackend(TraceBackend):
    def __init__(
        self,
        stream: TextIO | None = None,
        include_prompts: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self._stream = stream or sys.stdout
        self._include_prompts = include_prompts
        self._log = logger

    def start_trace(
        self,
        name: str,
        trace_id: str,
        metadata: dict | None = None,
    ) -> TraceContext:
        ctx = TraceContext(trace_id=trace_id, name=name, metadata=metadata or {})
        self._emit({
            "event": "trace.start",
            "trace_id": trace_id,
            "name": name,
            "metadata": ctx.metadata,
        })
        return ctx

    def end_trace(self, ctx: TraceContext, output: Any = None, error: str | None = None) -> None:
        self._emit({
            "event": "trace.end",
            "trace_id": ctx.trace_id,
            "name": ctx.name,
            "error": error,
        })

    def start_generation(
        self,
        trace: TraceContext,
        name: str,
        role: str,
        model: str,
        input: dict,
        metadata: dict | None = None,
    ) -> GenerationContext:
        gen = GenerationContext(
            trace=trace,
            name=name,
            role=role,
            model=model,
            input=input,
            metadata=metadata or {},
        )
        payload = {
            "event": "generation.start",
            "trace_id": trace.trace_id,
            "name": name,
            "role": role,
            "model": model,
        }
        if self._include_prompts:
            payload["input"] = input
        else:
            payload["input_chars"] = {
                k: len(v) if isinstance(v, str) else None for k, v in input.items()
            }
        self._emit(payload)
        return gen

    def end_generation(
        self,
        gen: GenerationContext,
        output: str | None = None,
        usage: dict | None = None,
        error: str | None = None,
    ) -> None:
        payload = {
            "event": "generation.end",
            "trace_id": gen.trace.trace_id,
            "name": gen.name,
            "role": gen.role,
            "model": gen.model,
            "usage": usage,
            "error": error,
        }
        if self._include_prompts:
            payload["output"] = output
        else:
            payload["output_chars"] = len(output) if isinstance(output, str) else None
        self._emit(payload)

    def _emit(self, payload: dict) -> None:
        payload = {"ts": datetime.utcnow().isoformat() + "Z", **payload}
        line = json.dumps(payload, ensure_ascii=False, default=str)
        if self._log is not None:
            self._log.info(line)
        else:
            print(line, file=self._stream, flush=True)
