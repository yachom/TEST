"""QAFlow — Analyze → Retrieve → Synthesize → Verify 루프.

종료: Verifier pass / 재시도 한도 도달.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext
from core.agents.exploration.flow import _coerce_context

if TYPE_CHECKING:
    from core.agents.qa.analyzer import Analyzer
    from core.agents.qa.retriever import QARetriever
    from core.agents.qa.synthesizer import Synthesizer
    from core.agents.qa.verifier import Verifier


MAX_RETRIES = 2


class QAFlow(Agent):
    @property
    def name(self) -> str:
        return "qa.flow"

    def __init__(
        self,
        analyzer: "Analyzer",
        retriever: "QARetriever",
        synthesizer: "Synthesizer",
        verifier: "Verifier",
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._analyzer = analyzer
        self._retriever = retriever
        self._synthesizer = synthesizer
        self._verifier = verifier
        self._max_retries = max_retries
        self._graph = self._build_graph()

    def run(self, ctx: AgentContext) -> AgentContext:
        ctx.artifacts.setdefault("synth_attempt", 0)
        final = self._graph.invoke(ctx)
        return _coerce_context(final, fallback=ctx)

    def _build_graph(self):
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(AgentContext)
        graph.add_node("analyze", self._analyze_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("synthesize", self._synthesize_node)
        graph.add_node("verify", self._verify_node)

        graph.add_edge(START, "analyze")
        graph.add_edge("analyze", "retrieve")
        graph.add_edge("retrieve", "synthesize")
        graph.add_edge("synthesize", "verify")
        graph.add_conditional_edges(
            "verify",
            self._route_after_verify,
            {"retry": "synthesize", "done": END},
        )
        return graph.compile()

    def _analyze_node(self, ctx: AgentContext) -> AgentContext:
        return self._analyzer.run(ctx)

    def _retrieve_node(self, ctx: AgentContext) -> AgentContext:
        return self._retriever.run(ctx)

    def _synthesize_node(self, ctx: AgentContext) -> AgentContext:
        ctx.artifacts["synth_attempt"] = ctx.artifacts.get("synth_attempt", 0) + 1
        return self._synthesizer.run(ctx)

    def _verify_node(self, ctx: AgentContext) -> AgentContext:
        return self._verifier.run(ctx)

    def _route_after_verify(self, ctx: AgentContext) -> str:
        if ctx.artifacts.get("verifier_decision") == "pass":
            return "done"
        if ctx.artifacts.get("synth_attempt", 0) >= self._max_retries:
            return "done"
        return "retry"
