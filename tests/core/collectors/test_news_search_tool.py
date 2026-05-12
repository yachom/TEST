"""뉴스 검색 Tool 테스트."""
import pytest

from core.application.collection_service import NewsSearchApplicationService
from core.collectors.news.models import SearchGroup, SearchPlan, SearchQuery
from core.collectors.news.normalizer import NewsNormalizer
from core.collectors.news.mock import MockNewsSearchProvider
from core.collectors.news.repositories.in_memory.in_memory_news_repository import InMemoryNewsRepository
from core.shared.domain.asset import AssetClass, AssetFamily, ASSET_CLASS_TO_FAMILY


class SimpleNewsSearchTool:
    """테스트용 간단한 뉴스 검색 Tool 래퍼."""

    def __init__(self, search_service: NewsSearchApplicationService) -> None:
        self._search_service = search_service

    def run(self, keyword: str, asset_class: str | None = None, save: bool = True):
        parsed_class = None
        if asset_class:
            try:
                parsed_class = AssetClass(asset_class)
            except ValueError:
                pass

        asset_family = None
        if parsed_class:
            asset_family = ASSET_CLASS_TO_FAMILY.get(parsed_class)

        query = SearchQuery(
            text=keyword,
            group_name="tool_search",
            provider="naver",
            asset_family=asset_family,
            asset_class=parsed_class,
            max_display=10,
        )
        plan = SearchPlan(groups=[], queries=[query], estimated_calls=1, provider_breakdown={"naver": 1})
        return self._search_service.execute(plan, save=save)


@pytest.fixture
def tool():
    provider = MockNewsSearchProvider(items_per_query=3)
    repo = InMemoryNewsRepository()
    svc = NewsSearchApplicationService(
        provider_registry={"naver": provider},
        normalizer=NewsNormalizer(),
        repository=repo,
    )
    return SimpleNewsSearchTool(svc), repo


def test_tool_save_mode_persists(tool):
    t, repo = tool
    result = t.run("상가 임대료", save=True)
    assert result.new_saved == 3


def test_tool_no_save_mode_does_not_persist(tool):
    t, repo = tool
    result = t.run("상가 임대료", save=False)
    assert result.total_fetched == 3
    assert repo.count() == 0


def test_tool_asset_class_parsed(tool):
    t, _ = tool
    result = t.run("상가", asset_class="commercial", save=False)
    assert result.total_fetched == 3


def test_tool_duplicate_not_saved_twice(tool):
    t, repo = tool
    t.run("상가 임대료", save=True)
    result2 = t.run("상가 임대료", save=True)
    assert result2.url_duplicates == 3
    assert repo.count() == 3
