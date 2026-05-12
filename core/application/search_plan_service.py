"""검색 설정 로드 + 검색 계획 생성 서비스."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from core.shared.domain.asset import AssetClass, AssetFamily
from core.collectors.news.models import SearchGroup, SearchQuery, SearchPlan


class SearchConfigService:
    """설정 파일을 로드하고 도메인 객체로 변환한다."""

    def __init__(self, config_path: str | Path) -> None:
        self._config_path = Path(config_path)
        self._raw: dict = {}

    def load(self) -> None:
        with open(self._config_path, encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)

    def get_active_groups(self) -> list[SearchGroup]:
        groups = []
        for g in self._raw.get("groups", []):
            if not g.get("active", True):
                continue
            groups.append(self._parse_group(g))
        return sorted(groups, key=lambda g: g.priority)

    def get_active_asset_classes(self) -> list[AssetClass]:
        active = self._raw.get("active_asset_classes", [])
        result = []
        for a in active:
            try:
                result.append(AssetClass(a))
            except ValueError:
                pass
        return result

    def _parse_group(self, raw: dict) -> SearchGroup:
        asset_family = self._to_asset_family(raw.get("asset_family"))
        asset_class = self._to_asset_class(raw.get("asset_class"))

        queries = [
            SearchQuery(
                text=q if isinstance(q, str) else q["text"],
                group_name=raw["name"],
                provider=raw.get("provider", "naver"),
                asset_family=asset_family,
                asset_class=asset_class,
                max_display=raw.get("max_display", 10),
                max_pages=raw.get("max_pages", 1),
                sort=raw.get("sort", "date"),
                active=True,
            )
            for q in raw.get("queries", [])
        ]

        return SearchGroup(
            name=raw["name"],
            active=raw.get("active", True),
            priority=raw.get("priority", 99),
            schedule_type=raw.get("schedule_type", "daily"),
            provider=raw.get("provider", "naver"),
            queries=queries,
            asset_family=asset_family,
            asset_class=asset_class,
            max_display=raw.get("max_display", 10),
            max_pages=raw.get("max_pages", 1),
            sort=raw.get("sort", "date"),
            post_process=raw.get("post_process", True),
            enable_llm_tagging=raw.get("enable_llm_tagging", True),
        )

    @staticmethod
    def _to_asset_family(value: Optional[str]) -> Optional[AssetFamily]:
        if not value:
            return None
        try:
            return AssetFamily(value)
        except ValueError:
            return None

    @staticmethod
    def _to_asset_class(value: Optional[str]) -> Optional[AssetClass]:
        if not value:
            return None
        try:
            return AssetClass(value)
        except ValueError:
            return None


class SearchPlanService:
    """활성 검색 그룹으로부터 SearchPlan을 생성한다."""

    def build(self, active_groups: list[SearchGroup]) -> SearchPlan:
        queries: list[SearchQuery] = []
        provider_breakdown: dict[str, int] = {}

        for group in active_groups:
            for query in group.queries:
                if not query.active:
                    continue
                queries.append(query)
                calls = query.max_pages
                provider_breakdown[query.provider] = provider_breakdown.get(query.provider, 0) + calls

        estimated_calls = sum(provider_breakdown.values())

        return SearchPlan(
            groups=active_groups,
            queries=queries,
            estimated_calls=estimated_calls,
            provider_breakdown=provider_breakdown,
        )
