"""End-to-end smoke test — Orchestrator 가 주소 입력으로 보고서까지 만들어내는지.

Stub LLM + Mock 도구로 흐름이 끝까지 흘러가는지만 검증.
구체적 보고서 내용 / LLM 응답은 검증 대상 아님.
"""
from __future__ import annotations

from core.reporting.qa_service import QAService
from core.shared.domain.asset import AssetClass
from interfaces.composition import (
    build_address_analysis_orchestrator,
    get_profile_by_asset_class,
)


def test_orchestrator_end_to_end():
    profile = get_profile_by_asset_class(AssetClass.COMMERCIAL)
    orchestrator = build_address_analysis_orchestrator(profile, use_stub_llm=True)

    result = orchestrator.analyze("강남구 역삼동 123-45")

    assert result.scope_id.startswith("analysis_")
    assert result.report["scope_id"] == result.scope_id
    assert result.report["node_count"] >= 1
    assert "Address" in result.report["nodes_by_label"]

    actors = {step.actor for step in result.evidence.steps}
    assert "exploration.planner" in actors
    assert "exploration.critic" in actors


def test_orchestrator_then_qa():
    profile = get_profile_by_asset_class(AssetClass.COMMERCIAL)
    orchestrator = build_address_analysis_orchestrator(profile, use_stub_llm=True)
    result = orchestrator.analyze("강남구 역삼동 123-45")

    qa = QAService(result.qa_flow)
    answer = qa.ask(result.scope_id, "이 자산의 임대수익률은?")

    assert answer["scope_id"] == result.scope_id
    assert answer["verifier_decision"] == "pass"
    assert answer["evidence_steps"] >= 4
