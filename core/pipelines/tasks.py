"""DAG에서 재사용할 공통 Task 함수.

각 자산의 DAG는 이 함수들을 조합하여 파이프라인을 구성한다.
비즈니스 로직은 core/application/ 및 core/processors/ 에 있다.
Task 함수는 의존성 조립을 interfaces/composition.py에 위임한다.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.shared.domain.evaluation import AssetProfile


def load_config_task(profile: "AssetProfile") -> dict:
    """Task 1 — AssetProfile 기반 검색 설정 로드."""
    from interfaces.composition import build_pipeline_from_profile
    pipeline = build_pipeline_from_profile(profile)
    pipeline["config"].load()
    groups = pipeline["config"].get_active_groups()
    return {"group_count": len(groups), "run_id": str(uuid.uuid4()), "asset_class": profile.asset_class.value}


def build_plan_task(config_result: dict) -> dict:
    """Task 2 — 검색 계획 생성."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(config_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    pipeline["config"].load()
    groups = pipeline["config"].get_active_groups()
    plan = pipeline["plan"].build(groups)
    return {
        "estimated_calls": plan.estimated_calls,
        "total_queries": plan.total_queries,
        "provider_breakdown": plan.provider_breakdown,
        "run_id": config_result["run_id"],
        "asset_class": config_result["asset_class"],
    }


def check_quota_task(plan_result: dict) -> dict:
    """Task 3 — API 호출 예산 확인."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(plan_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    quota = pipeline["quota"]
    breakdown: dict = plan_result["provider_breakdown"]
    can_run = all(quota.can_execute(provider, calls) for provider, calls in breakdown.items())
    if not can_run:
        raise RuntimeError("API 호출 한도 부족 — DAG 실행 중단")
    return {**plan_result, "quota_ok": True}


def search_and_save_task(quota_result: dict) -> dict:
    """Task 4+5 — 뉴스 검색 및 저장."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(quota_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    pipeline["config"].load()
    groups = pipeline["config"].get_active_groups()
    plan = pipeline["plan"].build(groups)
    result = pipeline["search"].execute(plan, save=True)
    pipeline["summary"].start(quota_result["run_id"])
    pipeline["summary"].record_search(result)
    return {"run_id": quota_result["run_id"], "new_saved": result.new_saved, "asset_class": quota_result["asset_class"]}


def rule_filter_task(search_result: dict) -> dict:
    """Task 6 — 룰 기반 필터링."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(search_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    results = pipeline["filter"].run_batch()
    pipeline["summary"].record_filter(results)
    passed = sum(1 for r in results if r.passed)
    return {**search_result, "filter_passed": passed}


def embed_task(filter_result: dict) -> dict:
    """Task 7 — 임베딩 생성."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(filter_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    results = pipeline["embedding"].run_batch()
    pipeline["summary"].record_embedding(results)
    return {**filter_result, "embedded": len(results)}


def dedup_task(embed_result: dict) -> dict:
    """Task 8 — 의미 중복 제거."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(embed_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    results = pipeline["dedup"].run_batch()
    pipeline["summary"].record_dedup(results)
    novel = sum(1 for r in results if r.is_novel)
    return {**embed_result, "novel": novel}


def llm_tag_task(dedup_result: dict) -> dict:
    """Task 9 — LLM 온톨로지 태깅."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(dedup_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    results = pipeline["tagging"].run_batch()
    pipeline["summary"].record_tagging(results)
    ok = sum(1 for r in results if r.success)
    return {**dedup_result, "tagged": ok}


def build_graph_signals_task(tag_result: dict) -> dict:
    """Task 10 — Signal Graph 적재."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(tag_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    candidates = pipeline["graph"].run_batch()
    pipeline["summary"].record_graph(candidates)
    queued = sum(1 for c in candidates if c.is_graph_eligible)
    return {**tag_result, "graph_queued": queued}


def save_summary_task(graph_result: dict) -> None:
    """Task 11 — 실행 요약 저장."""
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    from core.shared.domain.asset import AssetClass
    asset_class = AssetClass(graph_result["asset_class"])
    profile = get_profile_by_asset_class(asset_class)
    pipeline = build_pipeline_from_profile(profile)
    summary = pipeline["summary"].finish()
    if summary:
        print(f"[RunSummary] run_id={summary.run_id} elapsed={summary.elapsed_seconds:.1f}s")
        print(f"  search={summary.search} filter={summary.filter}")
        print(f"  dedup={summary.dedup} tagging={summary.tagging} graph={summary.graph}")
