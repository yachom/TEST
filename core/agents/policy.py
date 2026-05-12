"""에이전트 정책 게이트 — 도구 호출 / 비용 / 루프 통제.

자율 에이전트(ExplorerFlow, QAFlow)가 도구 호출 전 PolicyGate.check() 호출.
통과 시 도구 실행 후 PolicyGate.record() 로 누적.

allowed_tools 는 AssetProfile 에서 주입한다 — 자산이 노출 허용한 도구 목록.

비용 추적은 두 경로로 이루어진다:
  - 명시적 cost(USD) — 도구 호출의 알려진 단가
  - LLMResponse.usage — 토큰 사용량을 모델 단가표로 USD 환산

모델 단가표는 core/llm/pricing.yaml 에서 로드 (core.llm.pricing).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 단가 계산은 core.llm.pricing 으로 위임 — 단가표는 yaml 에서 관리.
from core.llm.pricing import estimate_llm_cost_usd  # re-export

__all__ = [
    "estimate_llm_cost_usd",
    "AgentPolicy",
    "PolicyDecision",
    "PolicyGate",
]


@dataclass
class AgentPolicy:
    """에이전트 자율성 한도."""
    max_tool_calls: int = 10
    max_cost_usd: float = 1.0
    allowed_tools: list[str] = field(default_factory=list)
    require_rationale: bool = True


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""


class PolicyGate:
    """도구 호출 전 정책 검사 + 누적 카운터.

    Flow 시작 시 새 인스턴스 생성 또는 reset() 호출.
    allowed_tools 가 비어있으면 도구 이름 제한 없음 (다른 한도만 적용).
    """

    def __init__(self, policy: AgentPolicy) -> None:
        self._policy = policy
        self._call_count = 0
        self._cost_used = 0.0
        self._input_tokens = 0
        self._output_tokens = 0

    def check(
        self,
        tool_name: str,
        rationale: Optional[str] = None,
        estimated_cost: float = 0.0,
    ) -> PolicyDecision:
        if self._policy.allowed_tools and tool_name not in self._policy.allowed_tools:
            return PolicyDecision(False, f"tool '{tool_name}' not in allowed_tools")
        if self._call_count >= self._policy.max_tool_calls:
            return PolicyDecision(False, f"max_tool_calls={self._policy.max_tool_calls} reached")
        if self._cost_used + estimated_cost > self._policy.max_cost_usd:
            return PolicyDecision(False, f"max_cost_usd={self._policy.max_cost_usd} would be exceeded")
        if self._policy.require_rationale and not rationale:
            return PolicyDecision(False, "rationale required but missing")
        return PolicyDecision(True)

    def record(
        self,
        cost: float = 0.0,
        usage: Optional[dict] = None,
        model: Optional[str] = None,
    ) -> None:
        """도구 호출 / LLM 호출 비용 누적.

        cost 가 명시되면 그대로 사용. usage 가 제공되면 모델 단가로 USD 환산해서 추가.
        usage 토큰은 별도 누적해서 관측 가능하게 유지.
        """
        self._call_count += 1
        self._cost_used += cost
        if usage:
            self._cost_used += estimate_llm_cost_usd(model or "stub", usage)
            self._input_tokens += int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
            self._output_tokens += int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def cost_used(self) -> float:
        return self._cost_used

    @property
    def input_tokens(self) -> int:
        return self._input_tokens

    @property
    def output_tokens(self) -> int:
        return self._output_tokens

    def is_at_limit(self) -> bool:
        return (
            self._call_count >= self._policy.max_tool_calls
            or self._cost_used >= self._policy.max_cost_usd
        )

    def reset(self) -> None:
        self._call_count = 0
        self._cost_used = 0.0
        self._input_tokens = 0
        self._output_tokens = 0
