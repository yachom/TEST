"""QAService — QAFlow 를 감싸 외부 호출 인터페이스 제공.

scope_id 와 사용자 질문을 받아 답변 + 근거를 반환.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import AgentContext

if TYPE_CHECKING:
    from core.agents.qa.flow import QAFlow


class QAService:
    def __init__(self, qa_flow: "QAFlow") -> None:
        self._qa = qa_flow

    def ask(self, scope_id: str, question: str) -> dict:
        ctx = AgentContext(
            scope_id=scope_id,
            inputs={"question": question},
        )
        result = self._qa.run(ctx)
        return {
            "scope_id": scope_id,
            "question": question,
            "answer": result.artifacts.get("answer_draft", ""),
            "citations": result.artifacts.get("citations", []),
            "verifier_decision": result.artifacts.get("verifier_decision", ""),
            "evidence_steps": len(result.evidence),
        }
