"""ExplorationFlow / QAFlow / Orchestrator smoke tests.

StubLLMClient 가 빈 응답을 주면 각 서브 에이전트가 안전 기본값으로 진행하는지,
LangGraph 가 종료 조건에 도달하는지를 검증.
"""
from __future__ import annotations

import pytest

from core.agents.base import AgentContext
from core.agents.exploration.critic import Critic
from core.agents.exploration.flow import ExplorationFlow
from core.agents.exploration.planner import Planner
from core.agents.exploration.retriever import Retriever
from core.agents.policy import AgentPolicy, PolicyGate
from core.agents.qa.analyzer import Analyzer
from core.agents.qa.flow import QAFlow
from core.agents.qa.retriever import QARetriever
from core.agents.qa.synthesizer import Synthesizer
from core.agents.qa.verifier import Verifier
from core.llm.catalog import PromptCatalog
from core.shared.infra.llm_client import StubLLMClient
from core.shared.stores.graph_store import InMemoryGraphStore


_CATALOG = PromptCatalog()


class _StubReportStore:
    def get_latest(self, scope_id: str):
        return None


class _StubSignalStore:
    pass


def _build_exploration_flow() -> ExplorationFlow:
    llm = StubLLMClient()
    policy = AgentPolicy(max_tool_calls=5, allowed_tools=["news_search_tool"])
    gate = PolicyGate(policy)
    return ExplorationFlow(
        planner=Planner(llm, allowed_tools=policy.allowed_tools, prompt_catalog=_CATALOG),
        retriever=Retriever(tool_registry={}, gate=gate),
        critic=Critic(llm, prompt_catalog=_CATALOG),
        gate=gate,
    )


def _build_qa_flow() -> QAFlow:
    llm = StubLLMClient()
    return QAFlow(
        analyzer=Analyzer(llm, prompt_catalog=_CATALOG),
        retriever=QARetriever(
            graph_store=InMemoryGraphStore(),
            report_store=_StubReportStore(),
            signal_store=_StubSignalStore(),
        ),
        synthesizer=Synthesizer(llm, prompt_catalog=_CATALOG),
        verifier=Verifier(llm, prompt_catalog=_CATALOG),
    )


def test_exploration_flow_terminates_with_stub_llm():
    flow = _build_exploration_flow()
    ctx = AgentContext(
        scope_id="analysis_test_001",
        inputs={"address": "강남구 역삼동 123-45"},
        artifacts={"initial_collection": [{"sample": "raw"}]},
    )
    result = flow.run(ctx)

    assert result.artifacts.get("critic_decision") == "sufficient"
    assert result.artifacts.get("iteration", 0) >= 1
    actors = {step.actor for step in result.evidence.steps}
    assert "exploration.planner" in actors
    assert "exploration.critic" in actors


def test_qa_flow_terminates_with_stub_llm():
    flow = _build_qa_flow()
    ctx = AgentContext(
        scope_id="analysis_test_002",
        inputs={"question": "이 자산의 임대수익률은 어떻게 평가됐나요?"},
    )
    result = flow.run(ctx)

    assert result.artifacts.get("verifier_decision") == "pass"
    assert "answer_draft" in result.artifacts
    assert len(result.evidence) >= 4  # analyze + retrieve + synthesize + verify


def test_policy_gate_blocks_disallowed_tool():
    policy = AgentPolicy(max_tool_calls=5, allowed_tools=["allowed_tool"])
    gate = PolicyGate(policy)

    decision = gate.check("disallowed_tool", rationale="test")
    assert not decision.allowed
    assert "not in allowed_tools" in decision.reason


def test_policy_gate_blocks_when_at_limit():
    policy = AgentPolicy(max_tool_calls=2, allowed_tools=[])
    gate = PolicyGate(policy)
    gate.record()
    gate.record()

    assert gate.is_at_limit()
    decision = gate.check("any_tool", rationale="test")
    assert not decision.allowed
