"""ExplorationFlow — Plan → Retrieve → Critic 루프.

LangGraph StateGraph 기반. 외부에서 보면 Agent ABC 구현 (run(ctx) 한 줄).
종료: Critic 충분 / 최대 반복 도달 / PolicyGate 한도.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.base import Agent, AgentContext, EvidenceTrace


def _coerce_context(value, fallback: AgentContext) -> AgentContext:
    if isinstance(value, AgentContext):
        return value
    if isinstance(value, dict):
        return AgentContext(
            scope_id=value.get("scope_id", fallback.scope_id),
            inputs=value.get("inputs", fallback.inputs),
            artifacts=value.get("artifacts", fallback.artifacts),
            evidence=value.get("evidence") or fallback.evidence,
        )
    return fallback

if TYPE_CHECKING:
    from core.agents.exploration.critic import Critic
    from core.agents.exploration.planner import Planner
    from core.agents.exploration.retriever import Retriever
    from core.agents.policy import PolicyGate


MAX_ITERATIONS = 3


class ExplorationFlow(Agent):
    @property
    def name(self) -> str:
        return "exploration.flow"

    def __init__(
        self,
        planner: "Planner",
        retriever: "Retriever",
        critic: "Critic",
        gate: "PolicyGate",
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        self._planner = planner
        self._retriever = retriever
        self._critic = critic
        self._gate = gate
        self._max_iterations = max_iterations
        self._graph = self._build_graph()

    def run(self, ctx: AgentContext) -> AgentContext:
        ctx.artifacts.setdefault("iteration", 0)
        final = self._graph.invoke(ctx)
        return _coerce_context(final, fallback=ctx)

    def _build_graph(self):
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(AgentContext)
        graph.add_node("plan", self._plan_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("critic", self._critic_node)

        graph.add_edge(START, "plan")
        graph.add_edge("plan", "retrieve")
        graph.add_edge("retrieve", "critic")
        graph.add_conditional_edges(
            "critic",
            self._route_after_critic,
            {"replan": "plan", "done": END},
        )
        return graph.compile()

    def _plan_node(self, ctx: AgentContext) -> AgentContext:
        return self._planner.run(ctx)

    def _retrieve_node(self, ctx: AgentContext) -> AgentContext:
        return self._retriever.run(ctx)

    def _critic_node(self, ctx: AgentContext) -> AgentContext:
        ctx.artifacts["iteration"] = ctx.artifacts.get("iteration", 0) + 1
        return self._critic.run(ctx)

    def _route_after_critic(self, ctx: AgentContext) -> str:
        if ctx.artifacts.get("critic_decision") == "sufficient":
            return "done"
        if ctx.artifacts.get("iteration", 0) >= self._max_iterations:
            return "done"
        if self._gate.is_at_limit():
            return "done"
        return "replan"
