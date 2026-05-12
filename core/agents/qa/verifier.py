"""Verifier — 답변 초안의 근거 정합성 검증.

출력: ctx.artifacts["verifier_decision"] = "pass" | "fail"
       ctx.artifacts["verifier_feedback"] = str (실패 시 재시도용)

Prompt: core.llm.PromptCatalog "qa.verifier".
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceStep

if TYPE_CHECKING:
    from core.llm.catalog import PromptCatalog
    from core.shared.infra.llm_client import LLMClient


_PROMPT_KEY = "qa.verifier"


class Verifier(Agent):
    @property
    def name(self) -> str:
        return "qa.verifier"

    def __init__(self, llm_client: "LLMClient", prompt_catalog: "PromptCatalog") -> None:
        self._llm = llm_client
        self._catalog = prompt_catalog

    def run(self, ctx: AgentContext) -> AgentContext:
        draft = ctx.artifacts.get("answer_draft", "")
        citations = ctx.artifacts.get("citations", [])
        evidence = ctx.artifacts.get("qa_evidence", [])

        rendered = self._catalog.render(
            _PROMPT_KEY,
            draft=draft,
            citations=str(citations),
            evidence=str(evidence),
        )
        response = self._llm.call(rendered.to_llm_request())
        parsed = response.parsed or {}
        decision = parsed.get("decision", "pass")
        feedback = parsed.get("feedback", "")

        ctx.artifacts["verifier_decision"] = decision
        ctx.artifacts["verifier_feedback"] = feedback

        ctx.evidence.append(EvidenceStep(
            step_id=ctx.evidence.next_step_id(),
            actor=self.name,
            tool_name="llm",
            rationale="verify answer against evidence",
            input_summary={
                "draft_length": len(draft),
                "citation_count": len(citations),
                "prompt_version": rendered.version_hash,
            },
            result_summary={"decision": decision},
        ))
        return ctx
