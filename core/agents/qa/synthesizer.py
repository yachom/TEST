"""Synthesizer — 검색 결과를 종합하여 답변 초안 작성.

출력: ctx.artifacts["answer_draft"] = str
입력 (재시도 시): ctx.artifacts["verifier_feedback"] = str

Prompt: core.llm.PromptCatalog "qa.synthesizer".
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceStep

if TYPE_CHECKING:
    from core.llm.catalog import PromptCatalog
    from core.shared.infra.llm_client import LLMClient


_PROMPT_KEY = "qa.synthesizer"


class Synthesizer(Agent):
    @property
    def name(self) -> str:
        return "qa.synthesizer"

    def __init__(self, llm_client: "LLMClient", prompt_catalog: "PromptCatalog") -> None:
        self._llm = llm_client
        self._catalog = prompt_catalog

    def run(self, ctx: AgentContext) -> AgentContext:
        question = ctx.inputs.get("question", "")
        qa_evidence = ctx.artifacts.get("qa_evidence", [])
        feedback = ctx.artifacts.get("verifier_feedback", "")

        feedback_section = (
            f"\nPrevious attempt failed verification: {feedback}" if feedback else ""
        )

        rendered = self._catalog.render(
            _PROMPT_KEY,
            question=question,
            evidence=str(qa_evidence),
            feedback_section=feedback_section,
        )
        response = self._llm.call(rendered.to_llm_request())
        parsed = response.parsed or {}
        ctx.artifacts["answer_draft"] = parsed.get("answer", "")
        ctx.artifacts["citations"] = parsed.get("citations", [])

        ctx.evidence.append(EvidenceStep(
            step_id=ctx.evidence.next_step_id(),
            actor=self.name,
            tool_name="llm",
            rationale="synthesize answer from evidence",
            input_summary={
                "question": question[:120],
                "is_retry": bool(feedback),
                "prompt_version": rendered.version_hash,
            },
            result_summary={"draft_length": len(ctx.artifacts["answer_draft"])},
        ))
        return ctx
