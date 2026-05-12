"""TracingLLMClient — LLMClient 데코레이터로 모든 호출에 observability 적용.

핵심 패턴:
    inner = LangChainLLMClient(settings)
    traced = TracingLLMClient(inner, backend=langfuse_backend, role="ontology_tagging")
    # 호출자(Planner, Tagger 등)는 LLMClient 인터페이스로만 받음 — 변경 0.

trace 컨텍스트는 contextvars 로 자동 전파:
    with trace_scope(backend, "address_analysis", scope_id):
        # 이 블록 내부의 모든 traced.call() 이 자동으로 같은 trace 에 첨부됨.
        orchestrator._exploration.run(ctx)

trace 밖에서 호출 시 (예: 단위 테스트, 임시 디버깅) backend 호출은 skip 하고 inner 만 실행.

PolicyGate 통합 (옵션):
    TracingLLMClient(inner, backend, role, policy_gate=gate)
    → call() 후 gate.record(usage=resp.usage, model=resp.model) 자동 호출.
    이로써 Planner/Critic/Analyzer/... 가 명시적으로 gate.record 안 해도 누적됨.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.shared.infra.llm_client import LLMClient, LLMRequest, LLMResponse
from core.shared.infra.observability.base import TraceBackend, current_trace

if TYPE_CHECKING:
    from core.agents.policy import PolicyGate


_log = logging.getLogger(__name__)


class TracingLLMClient(LLMClient):
    """LLMClient 를 감싸 모든 call() 을 TraceBackend 로 전송."""

    def __init__(
        self,
        inner: LLMClient,
        backend: TraceBackend,
        role: str,
        *,
        policy_gate: "PolicyGate | None" = None,
        generation_name: str | None = None,
    ) -> None:
        self._inner = inner
        self._backend = backend
        self._role = role
        self._policy_gate = policy_gate
        self._generation_name = generation_name or f"llm.{role}"

    def call(self, request: LLMRequest) -> LLMResponse:
        trace = current_trace()

        # 1) trace 컨텍스트 밖이면 그냥 통과 (observability 없이 실행).
        if trace is None:
            response = self._inner.call(request)
            self._record_policy(response)
            return response

        # 2) trace 컨텍스트 내부 — generation 으로 wrap.
        gen = None
        try:
            gen = self._backend.start_generation(
                trace=trace,
                name=self._generation_name,
                role=self._role,
                model=self._inner.model_name(),
                input={
                    "system": request.system_prompt,
                    "user": request.user_prompt,
                },
                metadata={
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "has_schema": request.response_schema is not None,
                },
            )
        except Exception as e:  # noqa: BLE001
            _log.warning("TracingLLMClient: start_generation failed: %s", e)

        try:
            response = self._inner.call(request)
        except Exception as exc:
            if gen is not None:
                try:
                    self._backend.end_generation(gen, output=None, error=str(exc))
                except Exception as e:  # noqa: BLE001
                    _log.warning("TracingLLMClient: end_generation(error) failed: %s", e)
            raise

        if gen is not None:
            try:
                self._backend.end_generation(
                    gen,
                    output=response.content,
                    usage=response.usage,
                )
            except Exception as e:  # noqa: BLE001
                _log.warning("TracingLLMClient: end_generation failed: %s", e)

        self._record_policy(response)
        return response

    def model_name(self) -> str:
        return self._inner.model_name()

    def _record_policy(self, response: LLMResponse) -> None:
        """PolicyGate 가 주입돼 있으면 usage / cost 자동 누적."""
        if self._policy_gate is None:
            return
        try:
            self._policy_gate.record(usage=response.usage or None, model=response.model or None)
        except Exception as e:  # noqa: BLE001
            _log.warning("TracingLLMClient: policy.record failed: %s", e)
