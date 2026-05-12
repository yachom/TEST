"""LangfuseBackend — Langfuse Cloud / Self-hosted 연결.

설치: pip install "fnpricing[observability]"  → langfuse 가져옴.

환경변수:
  LANGFUSE_PUBLIC_KEY (pk-lf-...)
  LANGFUSE_SECRET_KEY (sk-lf-...)
  LANGFUSE_HOST (기본: https://cloud.langfuse.com)

설계:
- langfuse SDK 의 Trace / Generation 객체를 backend_handle 에 저장.
- usage / cost 는 LLMResponse.usage 를 그대로 송신. Langfuse 가 모델 단가로 자동 환산.
- 한 trace 종료 시 flush 호출 — Langfuse SDK 가 background queue 로 묶어 전송.
- import 실패 / 키 미설정 시 NoOp 처럼 동작 (생성자에서 _disabled=True).

trace_id 매핑:
- Orchestrator scope_id (analysis_<uuid>) → Langfuse trace.id
- 자산 / 주소 / 사용자 등은 metadata 에 첨부 → Langfuse UI 에서 필터링 가능.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from core.shared.infra.observability.base import (
    GenerationContext,
    TraceBackend,
    TraceContext,
)


_log = logging.getLogger(__name__)


class LangfuseBackend(TraceBackend):
    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
        flush_at_trace_end: bool = True,
    ) -> None:
        self._public_key = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        self._secret_key = secret_key or os.environ.get("LANGFUSE_SECRET_KEY", "")
        self._host = host or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self._flush_at_trace_end = flush_at_trace_end
        self._client = None
        self._disabled = False

        if not (self._public_key and self._secret_key):
            _log.warning(
                "LangfuseBackend: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 미설정 — 비활성화."
            )
            self._disabled = True
            return

        try:
            # langfuse 2.x / 3.x 모두 호환되도록 lazy import
            from langfuse import Langfuse  # type: ignore

            self._client = Langfuse(
                public_key=self._public_key,
                secret_key=self._secret_key,
                host=self._host,
            )
        except Exception as e:  # noqa: BLE001
            _log.warning("LangfuseBackend: 클라이언트 초기화 실패 — 비활성화 (%s)", e)
            self._disabled = True

    # ------------------------------------------------------------------ trace

    def start_trace(
        self,
        name: str,
        trace_id: str,
        metadata: dict | None = None,
    ) -> TraceContext:
        ctx = TraceContext(trace_id=trace_id, name=name, metadata=metadata or {})
        if self._disabled or self._client is None:
            return ctx
        try:
            handle = self._client.trace(
                id=trace_id,
                name=name,
                metadata=ctx.metadata,
            )
            ctx.backend_handle = handle
        except Exception as e:  # noqa: BLE001
            _log.warning("LangfuseBackend.start_trace failed: %s", e)
        return ctx

    def end_trace(
        self,
        ctx: TraceContext,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        if self._disabled or ctx.backend_handle is None:
            return
        try:
            update_kwargs: dict[str, Any] = {}
            if output is not None:
                update_kwargs["output"] = output
            if error:
                update_kwargs["metadata"] = {**ctx.metadata, "error": error}
            if update_kwargs and hasattr(ctx.backend_handle, "update"):
                ctx.backend_handle.update(**update_kwargs)
        except Exception as e:  # noqa: BLE001
            _log.warning("LangfuseBackend.end_trace failed: %s", e)
        finally:
            if self._flush_at_trace_end:
                self.flush()

    # ------------------------------------------------------------- generation

    def start_generation(
        self,
        trace: TraceContext,
        name: str,
        role: str,
        model: str,
        input: dict,
        metadata: dict | None = None,
    ) -> GenerationContext:
        gen_meta = {"role": role, **(metadata or {})}
        gen = GenerationContext(
            trace=trace,
            name=name,
            role=role,
            model=model,
            input=input,
            metadata=gen_meta,
        )
        if self._disabled or trace.backend_handle is None:
            return gen
        try:
            handle = trace.backend_handle.generation(
                name=name,
                model=model,
                input=input,
                metadata=gen_meta,
            )
            gen.backend_handle = handle
        except Exception as e:  # noqa: BLE001
            _log.warning("LangfuseBackend.start_generation failed: %s", e)
        return gen

    def end_generation(
        self,
        gen: GenerationContext,
        output: str | None = None,
        usage: dict | None = None,
        error: str | None = None,
    ) -> None:
        if self._disabled or gen.backend_handle is None:
            return
        try:
            kwargs: dict[str, Any] = {}
            if output is not None:
                kwargs["output"] = output
            if usage is not None:
                # Langfuse usage 표준 키: input / output / total (or input_tokens 등 별칭 인식)
                kwargs["usage"] = _normalize_usage(usage)
            if error:
                kwargs["status_message"] = error
                kwargs["level"] = "ERROR"
            if kwargs and hasattr(gen.backend_handle, "end"):
                gen.backend_handle.end(**kwargs)
            elif kwargs and hasattr(gen.backend_handle, "update"):
                gen.backend_handle.update(**kwargs)
        except Exception as e:  # noqa: BLE001
            _log.warning("LangfuseBackend.end_generation failed: %s", e)

    # --------------------------------------------------------------- flushing

    def flush(self) -> None:
        if self._disabled or self._client is None:
            return
        try:
            self._client.flush()
        except Exception as e:  # noqa: BLE001
            _log.warning("LangfuseBackend.flush failed: %s", e)


def _normalize_usage(usage: dict) -> dict:
    """provider 별 usage 키를 Langfuse 가 인식하는 표준으로 변환."""
    if not usage:
        return {}
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    total = usage.get("total_tokens")
    if total is None and input_tokens is not None and output_tokens is not None:
        total = int(input_tokens) + int(output_tokens)
    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": total,
        "unit": "TOKENS",
    }
