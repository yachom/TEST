"""QA Retriever — 질문 분류에 따라 그래프 / 보고서 / 신호 검색.

evidence 에는 그래프 카운트가 아니라 직렬화된 노드/엣지 텍스트를 담는다 —
Synthesizer 가 실제 데이터를 보고 답하도록.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceStep
from core.reporting.graph_serializer import serialize_subgraph_for_llm

if TYPE_CHECKING:
    from core.shared.stores.graph_store import GraphStore
    from core.shared.stores.report_store import ReportStore
    from core.shared.stores.signal_store import SignalStore


class QARetriever(Agent):
    @property
    def name(self) -> str:
        return "qa.retriever"

    def __init__(
        self,
        graph_store: "GraphStore",
        report_store: "ReportStore",
        signal_store: "SignalStore",
    ) -> None:
        self._graph = graph_store
        self._report = report_store
        self._signal = signal_store

    def run(self, ctx: AgentContext) -> AgentContext:
        kind = ctx.artifacts.get("question_kind", "factual")
        evidence: list[dict] = []

        subgraph = self._graph.query_subgraph(ctx.scope_id)
        evidence.append({
            "source": "graph",
            "scope_id": ctx.scope_id,
            "node_count": len(subgraph.nodes),
            "relation_count": len(subgraph.relations),
            "graph_text": serialize_subgraph_for_llm(subgraph),
        })

        if kind in {"reasoning", "comparison"}:
            report = self._report.get_latest(ctx.scope_id) if hasattr(self._report, "get_latest") else None
            if report is not None:
                evidence.append({
                    "source": "report",
                    "report_id": report.get("id", ""),
                    "summary": report.get("summary", ""),
                })

        ctx.artifacts["qa_evidence"] = evidence

        ctx.evidence.append(EvidenceStep(
            step_id=ctx.evidence.next_step_id(),
            actor=self.name,
            tool_name="store_query",
            rationale=f"retrieve evidence for {kind} question",
            input_summary={"kind": kind, "scope_id": ctx.scope_id},
            result_summary={"evidence_sources": len(evidence)},
        ))
        return ctx
