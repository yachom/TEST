"""검색 설정 로드 테스트."""
import pytest
from pathlib import Path

from core.application.search_plan_service import SearchConfigService
from core.shared.domain.asset import AssetClass

CONFIG_PATH = Path(__file__).parents[3] / "projects" / "commercial_real_estate" / "config" / "search_groups.yaml"


@pytest.fixture
def svc():
    s = SearchConfigService(CONFIG_PATH)
    s.load()
    return s


def test_loads_without_error(svc):
    groups = svc.get_active_groups()
    assert len(groups) > 0


def test_inactive_groups_excluded(svc):
    groups = svc.get_active_groups()
    names = [g.name for g in groups]
    assert "residential_real_estate_market" not in names
    assert "logistics_market" not in names


def test_active_groups_have_queries(svc):
    for group in svc.get_active_groups():
        assert len(group.queries) > 0, f"{group.name} 에 검색어 없음"


def test_priority_ordering(svc):
    groups = svc.get_active_groups()
    priorities = [g.priority for g in groups]
    assert priorities == sorted(priorities)


def test_active_asset_classes(svc):
    classes = svc.get_active_asset_classes()
    assert AssetClass.COMMERCIAL in classes


def test_query_inherits_group_asset_class(svc):
    commercial_group = next(
        g for g in svc.get_active_groups()
        if g.name == "commercial_real_estate_market"
    )
    for q in commercial_group.queries:
        assert q.asset_class == AssetClass.COMMERCIAL
