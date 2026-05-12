"""Analyzer — 사용자 질문을 분류하고 필요 정보 식별.

출력: ctx.artifacts["question_kind"] = "factual" | "reasoning" | "comparison" | "temporal"
       ctx.artifacts["required_info"] = list[str]

Prompt: core.llm.PromptCatalog "qa.analyzer".
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceStep

if TYPE_CHECKING:
    from core.llm.catalog import PromptCatalog
    from core.shared.infra.llm_client import LLMClient


_PROMPT_KEY = "qa.analyzer"


class Analyzer(Agent):
    @property
    def name(self) -> str:
        return "qa.analyzer"

    def __init__(self, llm_client: "LLMClient", prompt_catalog: "PromptCatalog") -> None:
        self._llm = llm_client
        self._catalog = prompt_catalog

    def run(self, ctx: AgentContext) -> AgentContext:
        question = ctx.inputs.get("question", "")
        rendered = self._catalog.render(_PROMPT_KEY, question=question)
        response = self._llm.call(rendered.to_llm_request())
        parsed = response.parsed or {}
        kind = parsed.get("kind", "factual")
        required = parsed.get("required_info", [])

        ctx.artifacts["question_kind"] = kind
        ctx.artifacts["required_info"] = required

        ctx.evidence.append(EvidenceStep(
            step_id=ctx.evidence.next_step_id(),
            actor=self.name,
            tool_name="llm",
            rationale="classify question and identify required information",
            input_summary={
                "question": question[:120],
                "prompt_version": rendered.version_hash,
            },
            result_summary={"kind": kind, "required_count": len(required)},
        ))
        return ctx
