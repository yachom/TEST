"""DAG에서 재사용할 공통 Task 함수.

각 자산의 DAG는 이 함수들을 조합하여 파이프라인을 구성한다.
비즈니스 로직은 core/application/ 및 core/processors/ 에 있다.
Task 함수는 의존성 조립을 interfaces/composition.py에 위임한다.

시그니처 안정성 (2026-05-12):
  task 간 전달되는 상태는 PipelineState TypedDict 로 명시.
  fnpricing-batch 같은 외부 호출자 (Airflow DAG) 가 dict 키 오타 없이 사용하도록.
  total=False 라 모든 필드가 optional — 각 task 가 자기 단계에서 추가하는 필드만 채움.

  외부 (DAG) 는 다음을 import 하면 됨:
    from core.pipelines.tasks import (
        PipelineState,
        load_config_task, build_plan_task, ...,
    )
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from core.shared.domain.evaluation import AssetProfile


class PipelineState(TypedDict, total=False):
    """배치 파이프라인 task 간 전달되는 누적 상태.

    각 task 는 이전 state 를 받아 자기 단계에서 추가하는 필드를 spread 하여 반환.
    total=False — 모든 필드가 optional. 첫 task 부터 마지막 task 까지 누적.
    """
    # 모든 task 공통
    run_id: str
    asset_class: str

    # load_config_task
    group_count: int

    # build_plan_task
    estimated_calls: int
    total_queries: int
    provider_breakdown: dict

    # check_quota_task
    quota_ok: bool

    # search_and_save_task
    new_saved: int

    # rule_filter_task
    filter_passed: int

    # embed_task
    embedded: int

    # dedup_task
    novel: int

    # llm_tag_task
    tagged: int

    # build_graph_signals_task
    graph_queued: int


def _pipeline_for(asset_class_value: str):
    """공통 헬퍼 — asset_class 값으로 profile 조회 + pipeline 조립."""
    from core.shared.domain.asset import AssetClass
    from interfaces.composition import build_pipeline_from_profile, get_profile_by_asset_class
    asset_class = AssetClass(asset_class_value)
    profile = get_profile_by_asset_class(asset_class)
    return build_pipeline_from_profile(profile)


def load_config_task(profile: "AssetProfile") -> PipelineState:
    """Task 1 — AssetProfile 기반 검색 설정 로드."""
    from interfaces.composition import build_pipeline_from_profile
    pipeline = build_pipeline_from_profile(profile)
    pipeline["config"].load()
    groups = pipeline["config"].get_active_groups()
    return {
        "group_count": len(groups),
        "run_id": str(uuid.uuid4()),
        "asset_class": profile.asset_class.value,
    }


def build_plan_task(state: PipelineState) -> PipelineState:
    """Task 2 — 검색 계획 생성."""
    pipeline = _pipeline_for(state["asset_class"])
    pipeline["config"].load()
    groups = pipeline["config"].get_active_groups()
    plan = pipeline["plan"].build(groups)
    return {
        **state,
        "estimated_calls": plan.estimated_calls,
        "total_queries": plan.total_queries,
        "provider_breakdown": plan.provider_breakdown,
    }


def check_quota_task(state: PipelineState) -> PipelineState:
    """Task 3 — API 호출 예산 확인."""
    pipeline = _pipeline_for(state["asset_class"])
    quota = pipeline["quota"]
    breakdown: dict = state["provider_breakdown"]
    can_run = all(quota.can_execute(provider, calls) for provider, calls in breakdown.items())
    if not can_run:
        raise RuntimeError("API 호출 한도 부족 — DAG 실행 중단")
    return {**state, "quota_ok": True}


def search_and_save_task(state: PipelineState) -> PipelineState:
    """Task 4+5 — 뉴스 검색 및 저장."""
    pipeline = _pipeline_for(state["asset_class"])
    pipeline["config"].load()
    groups = pipeline["config"].get_active_groups()
    plan = pipeline["plan"].build(groups)
    result = pipeline["search"].execute(plan, save=True)
    pipeline["summary"].start(state["run_id"])
    pipeline["summary"].record_search(result)
    return {**state, "new_saved": result.new_saved}


def rule_filter_task(state: PipelineState) -> PipelineState:
    """Task 6 — 룰 기반 필터링."""
    pipeline = _pipeline_for(state["asset_class"])
    results = pipeline["filter"].run_batch()
    pipeline["summary"].record_filter(results)
    passed = sum(1 for r in results if r.passed)
    return {**state, "filter_passed": passed}


def embed_task(state: PipelineState) -> PipelineState:
    """Task 7 — 임베딩 생성."""
    pipeline = _pipeline_for(state["asset_class"])
    results = pipeline["embedding"].run_batch()
    pipeline["summary"].record_embedding(results)
    return {**state, "embedded": len(results)}


def dedup_task(state: PipelineState) -> PipelineState:
    """Task 8 — 의미 중복 제거."""
    pipeline = _pipeline_for(state["asset_class"])
    results = pipeline["dedup"].run_batch()
    pipeline["summary"].record_dedup(results)
    novel = sum(1 for r in results if r.is_novel)
    return {**state, "novel": novel}


def llm_tag_task(state: PipelineState) -> PipelineState:
    """Task 9 — LLM 온톨로지 태깅."""
    pipeline = _pipeline_for(state["asset_class"])
    results = pipeline["tagging"].run_batch()
    pipeline["summary"].record_tagging(results)
    ok = sum(1 for r in results if r.success)
    return {**state, "tagged": ok}


def build_graph_signals_task(state: PipelineState) -> PipelineState:
    """Task 10 — Signal Graph 적재."""
    pipeline = _pipeline_for(state["asset_class"])
    candidates = pipeline["graph"].run_batch()
    pipeline["summary"].record_graph(candidates)
    queued = sum(1 for c in candidates if c.is_graph_eligible)
    return {**state, "graph_queued": queued}


def save_summary_task(state: PipelineState) -> None:
    """Task 11 — 실행 요약 저장."""
    pipeline = _pipeline_for(state["asset_class"])
    summary = pipeline["summary"].finish()
    if summary:
        print(f"[RunSummary] run_id={summary.run_id} elapsed={summary.elapsed_seconds:.1f}s")
        print(f"  search={summary.search} filter={summary.filter}")
        print(f"  dedup={summary.dedup} tagging={summary.tagging} graph={summary.graph}")
