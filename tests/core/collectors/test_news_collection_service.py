"""뉴스 검색 → 저장 플로우 테스트 (Mock Provider 사용)."""
import pytest

from core.application.collection_service import NewsSearchApplicationService
from core.application.search_plan_service import SearchPlanService
from core.collectors.news.models import SearchGroup, SearchQuery
from core.collectors.news.normalizer import NewsNormalizer
from core.collectors.news.mock import MockNewsSearchProvider
from core.collectors.news.repositories.in_memory.in_memory_news_repository import InMemoryNewsRepository
from core.shared.domain.states import FilterStatus


@pytest.fixture
def service():
    provider = MockNewsSearchProvider(items_per_query=3)
    repo = InMemoryNewsRepository()
    return NewsSearchApplicationService(
        provider_registry={"naver": provider},
        normalizer=NewsNormalizer(),
        repository=repo,
    ), repo


def _make_plan(keyword: str = "상가 공실률"):
    query = SearchQuery(text=keyword, group_name="test", provider="naver")
    group = SearchGroup(name="test", active=True, priority=1, schedule_type="daily", provider="naver", queries=[query])
    return SearchPlanService().build([group])


def test_search_saves_new_articles(service):
    svc, repo = service
    plan = _make_plan()
    result = svc.execute(plan, save=True)
    assert result.new_saved == 3
    assert repo.count() == 3


def test_duplicate_url_not_saved_twice(service):
    svc, repo = service
    plan = _make_plan()
    svc.execute(plan, save=True)
    result2 = svc.execute(plan, save=True)
    assert result2.url_duplicates == 3
    assert repo.count() == 3


def test_no_save_mode_does_not_persist(service):
    svc, repo = service
    plan = _make_plan()
    result = svc.execute(plan, save=False)
    assert result.total_fetched == 3
    assert repo.count() == 0


def test_saved_articles_start_with_pending_filter(service):
    svc, repo = service
    plan = _make_plan()
    svc.execute(plan, save=True)
    for article in repo.all():
        assert article.filter_status == FilterStatus.PENDING
