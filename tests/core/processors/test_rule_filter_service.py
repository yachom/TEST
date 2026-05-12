"""룰 기반 필터링 테스트."""
import pytest

from core.processors.filters.rule_filter import RuleFilterService
from core.shared.domain.states import FilterStatus, FilterExcludeReason
from core.collectors.news.repositories.in_memory.in_memory_news_repository import InMemoryNewsRepository
from core.collectors.news.normalizer import NewsNormalizer
from core.collectors.news.models import SearchQuery


def _make_repo_with_articles(titles_descs: list[tuple[str, str]]) -> InMemoryNewsRepository:
    repo = InMemoryNewsRepository()
    normalizer = NewsNormalizer()
    query = SearchQuery(text="test", group_name="test", provider="naver")
    for title, desc in titles_descs:
        raw = {
            "title": title,
            "description": desc,
            "originallink": f"https://example.com/{hash(title)}",
            "link": "",
            "pubDate": "",
        }
        repo.save(normalizer.normalize(raw, query))
    return repo


@pytest.fixture
def svc(request):
    repo = request.param
    return RuleFilterService(
        repository=repo,
        signal_keywords=["상승", "하락", "위험", "규제", "감소", "폐업"],
        asset_keywords=["상가", "부동산", "소상공인"],
        min_text_length=10,
    ), repo


@pytest.mark.parametrize("svc", [
    _make_repo_with_articles([("상가 공실률 상승", "소상공인 폐업 증가로 상가 공실이 늘었다")])
], indirect=True)
def test_relevant_article_passes(svc):
    service, repo = svc
    results = service.run_batch()
    assert results[0].passed is True
    article = repo.all()[0]
    assert article.filter_status == FilterStatus.PASSED


@pytest.mark.parametrize("svc", [
    _make_repo_with_articles([("오늘의 날씨", "맑고 화창한 날씨가 예상됩니다")])
], indirect=True)
def test_irrelevant_article_excluded(svc):
    service, repo = svc
    results = service.run_batch()
    assert results[0].passed is False
    assert results[0].exclude_reason == FilterExcludeReason.IRRELEVANT_ASSET


@pytest.mark.parametrize("svc", [
    _make_repo_with_articles([("부동산 광고 PR", "협찬 분양 홍보 상가 매물")])
], indirect=True)
def test_ad_article_excluded(svc):
    service, repo = svc
    results = service.run_batch()
    assert results[0].passed is False
    assert results[0].exclude_reason == FilterExcludeReason.ADVERTISEMENT


@pytest.mark.parametrize("svc", [
    _make_repo_with_articles([
        ("상가 공실률 상승", "소상공인 폐업 증가"),
        ("오늘의 날씨", "맑음"),
        ("부동산 하락세", "상가 임대료 감소"),
    ])
], indirect=True)
def test_mixed_batch(svc):
    service, repo = svc
    results = service.run_batch()
    passed = [r for r in results if r.passed]
    excluded = [r for r in results if not r.passed]
    assert len(passed) == 2
    assert len(excluded) == 1


@pytest.mark.parametrize("svc", [
    _make_repo_with_articles([("상가 임대", "상가 위치")])
], indirect=True)
def test_no_signal_keyword_excluded(svc):
    service, repo = svc
    results = service.run_batch()
    assert results[0].passed is False
    assert results[0].exclude_reason == FilterExcludeReason.NO_SIGNAL_KEYWORD
