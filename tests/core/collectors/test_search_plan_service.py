"""검색 계획 생성 테스트."""
import pytest
from pathlib import Path

from core.application.search_plan_service import SearchConfigService, SearchPlanService

CONFIG_PATH = Path(__file__).parents[3] / "projects" / "commercial_real_estate" / "config" / "search_groups.yaml"


@pytest.fixture
def plan():
    config = SearchConfigService(CONFIG_PATH)
    config.load()
    groups = config.get_active_groups()
    return SearchPlanService().build(groups)


def test_plan_has_queries(plan):
    assert plan.total_queries > 0


def test_estimated_calls_positive(plan):
    assert plan.estimated_calls > 0


def test_provider_breakdown_matches_queries(plan):
    total_from_breakdown = sum(plan.provider_breakdown.values())
    assert total_from_breakdown == plan.estimated_calls


def test_plan_groups_match_active(plan):
    assert len(plan.groups) > 0
