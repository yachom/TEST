"""Retriever — Planner 의 계획에 따라 도구를 호출.

PolicyGate 가 호출 전 검사. 통과 시 도구 실행 + EvidenceStep 누적.
도구 자체는 BaseTool 인터페이스 (얇은 어댑터, Application Service 호출).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceStep

if TYPE_CHECKING:
    from core.agents.policy import PolicyGate
    from core.tools.base import BaseTool


class Retriever(Agent):
    @property
    def name(self) -> str:
        return "exploration.retriever"

    def __init__(self, tool_registry: dict[str, "BaseTool"], gate: "PolicyGate") -> None:
        self._tools = tool_registry
        self._gate = gate

    def run(self, ctx: AgentContext) -> AgentContext:
        plan = ctx.artifacts.get("plan", [])
        retrieved: list[dict] = ctx.artifacts.setdefault("retrieved", [])

        for call in plan:
            tool_name = call.get("tool", "")
            tool_input = call.get("input", {})
            rationale = call.get("rationale", "")

            decision = self._gate.check(tool_name, rationale=rationale)
            if not decision.allowed:
                ctx.evidence.append(EvidenceStep(
                    step_id=ctx.evidence.next_step_id(),
                    actor=self.name,
                    tool_name=tool_name,
                    rationale=rationale,
                    input_summary={"input": tool_input, "blocked": True},
                    result_summary={"reason": decision.reason},
                ))
                continue

            tool = self._tools.get(tool_name)
            if tool is None:
                ctx.evidence.append(EvidenceStep(
                    step_id=ctx.evidence.next_step_id(),
                    actor=self.name,
                    tool_name=tool_name,
                    rationale=rationale,
                    input_summary={"input": tool_input, "missing": True},
                    result_summary={"reason": "tool not registered"},
                ))
                continue

            try:
                result = tool.run(**tool_input)
            except Exception as exc:
                ctx.evidence.append(EvidenceStep(
                    step_id=ctx.evidence.next_step_id(),
                    actor=self.name,
                    tool_name=tool_name,
                    rationale=rationale,
                    input_summary={"input": tool_input},
                    result_summary={"error": str(exc)},
                ))
                continue
            self._gate.record()
            retrieved.append({"tool": tool_name, "result": result})
            ctx.evidence.append(EvidenceStep(
                step_id=ctx.evidence.next_step_id(),
                actor=self.name,
                tool_name=tool_name,
                rationale=rationale,
                input_summary={"input": tool_input},
                result_summary={"keys": list(result.keys()) if isinstance(result, dict) else []},
            ))

        return ctx
