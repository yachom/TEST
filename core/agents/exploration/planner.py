"""Planner — 1차 수집 결과 보고 추가 수집 계획 수립.

출력: ctx.artifacts["plan"] = [{"tool": str, "input": dict, "rationale": str}, ...]

Prompt 는 core.llm.PromptCatalog 의 "exploration.planner" 키에서 로드.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceStep

if TYPE_CHECKING:
    from core.llm.catalog import PromptCatalog
    from core.shared.infra.llm_client import LLMClient


_PROMPT_KEY = "exploration.planner"


class Planner(Agent):
    @property
    def name(self) -> str:
        return "exploration.planner"

    def __init__(
        self,
        llm_client: "LLMClient",
        allowed_tools: list[str],
        prompt_catalog: "PromptCatalog",
    ) -> None:
        self._llm = llm_client
        self._allowed_tools = allowed_tools
        self._catalog = prompt_catalog

    def run(self, ctx: AgentContext) -> AgentContext:
        initial = ctx.artifacts.get("initial_collection", [])
        retrieved = ctx.artifacts.get("retrieved", [])
        critic_feedback = ctx.artifacts.get("critic_feedback", "")

        address = ctx.inputs.get("address", "")
        tools_csv = ", ".join(self._allowed_tools) if self._allowed_tools else "(none)"

        retrieved_section = (
            f"\nAlready retrieved this round: {len(retrieved)} records" if retrieved else ""
        )
        feedback_section = (
            f"\nCritic feedback (re-plan): {critic_feedback}" if critic_feedback else ""
        )

        rendered = self._catalog.render(
            _PROMPT_KEY,
            tools=tools_csv,
            address=address,
            initial_count=len(initial),
            retrieved_section=retrieved_section,
            feedback_section=feedback_section,
        )
        response = self._llm.call(rendered.to_llm_request())
        plan = self._parse_plan(response.parsed or {})
        ctx.artifacts["plan"] = plan

        ctx.evidence.append(EvidenceStep(
            step_id=ctx.evidence.next_step_id(),
            actor=self.name,
            tool_name="llm",
            rationale="propose additional collection tools",
            input_summary={
                "initial_count": len(initial),
                "retrieved_count": len(retrieved),
                "iteration": critic_feedback != "",
                "prompt_version": rendered.version_hash,
            },
            result_summary={"planned_calls": len(plan)},
        ))
        return ctx

    @staticmethod
    def _parse_plan(parsed: dict) -> list[dict]:
        calls = parsed.get("calls", [])
        return [c for c in calls if isinstance(c, dict) and "tool" in c]
