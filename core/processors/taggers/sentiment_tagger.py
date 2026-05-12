"""감정평가 온톨로지 태깅 서비스.

Prompt + Schema: core.llm.PromptCatalog "tagging.sentiment" 에서 로드.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from core.collectors.news.models import TaggingResult
from core.processors.taggers.models import OntologyTag
from core.shared.domain.states import TagExcludeReason
from core.shared.domain.ontology_schema import (
    SignalType, InfluenceDirection, InfluenceStrength,
    InfluencePeriod, Applicability, AppliedScope,
)
from core.shared.domain.asset import AssetFamily, AssetClass

if TYPE_CHECKING:
    from core.collectors.news.repositories.news_repository import NewsRepository
    from core.collectors.news.repositories.ontology_tag_repository import OntologyTagRepository
    from core.llm.catalog import PromptCatalog
    from core.shared.infra.llm_client import LLMClient


_PROMPT_KEY = "tagging.sentiment"


class OntologyTaggingService:
    """의미상 신규 뉴스를 LLM 기반 온톨로지 태깅 대상으로 처리한다."""

    def __init__(
        self,
        news_repository: "NewsRepository",
        tag_repository: "OntologyTagRepository",
        llm_client: "LLMClient",
        prompt_catalog: "PromptCatalog",
        confidence_threshold: float = 0.7,
        evaluation_factors: list[str] | None = None,
    ) -> None:
        self._news_repo = news_repository
        self._tag_repo = tag_repository
        self._llm = llm_client
        self._catalog = prompt_catalog
        self._conf_threshold = confidence_threshold
        self._evaluation_factors = evaluation_factors or []

    def run_batch(self) -> list[TaggingResult]:
        pending = self._news_repo.find_pending_tag()
        results = []
        for article in pending:
            result = self._tag(article)
            if result.success and result.tag:
                self._tag_repo.save(result.tag)
            self._news_repo.update_tag_status(article.id, result)
            results.append(result)
        return results

    def _tag(self, article) -> TaggingResult:
        factors = (
            ", ".join(self._evaluation_factors) if self._evaluation_factors else "일반 시장 신호"
        )
        rendered = self._catalog.render(
            _PROMPT_KEY,
            factors=factors,
            title=article.title or "",
            description=article.description or "",
        )
        try:
            response = self._llm.call(rendered.to_llm_request())
        except Exception as e:
            return TaggingResult(article_id=article.id, success=False, error=str(e))

        parsed = response.parsed or {}
        if not parsed:
            return TaggingResult(
                article_id=article.id,
                success=False,
                exclude_reason=TagExcludeReason.INSUFFICIENT_INPUT,
            )

        confidence = parsed.get("confidence", 0.0)
        if confidence < self._conf_threshold:
            return TaggingResult(
                article_id=article.id,
                success=False,
                exclude_reason=TagExcludeReason.LOW_CONFIDENCE,
            )

        tag = self._parse_tag(article.id, parsed, response.model)
        return TaggingResult(article_id=article.id, success=True, tag=tag)

    @staticmethod
    def _parse_tag(article_id: str, parsed: dict, model: str) -> OntologyTag:
        return OntologyTag(
            article_id=article_id,
            asset_family=AssetFamily(parsed.get("asset_family", AssetFamily.REAL_ESTATE)),
            asset_class=AssetClass(parsed.get("asset_class", AssetClass.COMMERCIAL)),
            signal_type=SignalType(parsed.get("signal_type", SignalType.MARKET)),
            influence_direction=InfluenceDirection(
                parsed.get("influence_direction", InfluenceDirection.NEUTRAL)
            ),
            influence_strength=InfluenceStrength(
                parsed.get("influence_strength", InfluenceStrength.WEAK)
            ),
            influence_period=InfluencePeriod(
                parsed.get("influence_period", InfluencePeriod.SHORT)
            ),
            applicability=Applicability(
                parsed.get("applicability", Applicability.BACKGROUND_ONLY)
            ),
            applied_scope=AppliedScope(parsed.get("applied_scope", AppliedScope.NATIONAL)),
            affected_evaluation_factors=parsed.get("affected_evaluation_factors", []),
            affected_asset_subtypes=parsed.get("affected_asset_subtypes", []),
            event_type=parsed.get("event_type", "unknown"),
            summary=parsed.get("summary", ""),
            rationale=parsed.get("rationale", ""),
            confidence=parsed.get("confidence", 0.0),
            tagged_at=datetime.utcnow(),
            llm_model=model,
            raw_llm_response=str(parsed),
        )
