"""Critic — 누적 수집물의 충분성 평가.

출력: ctx.artifacts["critic_decision"] = "sufficient" | "needs_more"
       ctx.artifacts["critic_feedback"] = str (재계획 시 Planner 가 활용)

Prompt: core.llm.PromptCatalog "exploration.critic".
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceStep

if TYPE_CHECKING:
    from core.llm.catalog import PromptCatalog
    from core.shared.infra.llm_client import LLMClient


_PROMPT_KEY = "exploration.critic"


class Critic(Agent):
    @property
    def name(self) -> str:
        return "exploration.critic"

    def __init__(self, llm_client: "LLMClient", prompt_catalog: "PromptCatalog") -> None:
        self._llm = llm_client
        self._catalog = prompt_catalog

    def run(self, ctx: AgentContext) -> AgentContext:
        initial = ctx.artifacts.get("initial_collection", [])
        retrieved = ctx.artifacts.get("retrieved", [])

        rendered = self._catalog.render(
            _PROMPT_KEY,
            initial_count=len(initial),
            retrieved_count=len(retrieved),
        )
        response = self._llm.call(rendered.to_llm_request())
        parsed = response.parsed or {}
        decision = parsed.get("decision", "sufficient")
        feedback = parsed.get("feedback", "")

        ctx.artifacts["critic_decision"] = decision
        ctx.artifacts["critic_feedback"] = feedback

        ctx.evidence.append(EvidenceStep(
            step_id=ctx.evidence.next_step_id(),
            actor=self.name,
            tool_name="llm",
            rationale="evaluate sufficiency of collected information",
            input_summary={
                "initial_count": len(initial),
                "retrieved_count": len(retrieved),
                "prompt_version": rendered.version_hash,
            },
            result_summary={"decision": decision},
        ))
        return ctx
