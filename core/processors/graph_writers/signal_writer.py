"""GraphSignalService — OntologyTag → signal_store + GraphWriter."""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.processors.taggers.models import MarketSignalCandidate
from core.shared.domain.states import GraphStatus, GraphExcludeReason
from core.shared.domain.ontology_schema import Applicability
from core.shared.infra.graph_writer import GraphNode

if TYPE_CHECKING:
    from core.collectors.news.repositories.news_repository import NewsRepository
    from core.collectors.news.repositories.ontology_tag_repository import OntologyTagRepository
    from core.shared.stores.signal_store import SignalStore
    from core.shared.infra.graph_writer import GraphWriter


class GraphSignalService:
    """OntologyTag를 MarketSignalCandidate로 변환하고 Signal 저장소에 적재한다."""

    _INELIGIBLE_APPLICABILITIES = frozenset([Applicability.NOT_RELEVANT])

    def __init__(
        self,
        news_repository: "NewsRepository",
        tag_repository: "OntologyTagRepository",
        signal_store: "SignalStore",
        graph_writer: "GraphWriter",
        min_confidence: float = 0.7,
    ) -> None:
        self._news_repo = news_repository
        self._tag_repo = tag_repository
        self._signal_store = signal_store
        self._graph_writer = graph_writer
        self._min_confidence = min_confidence

    def run_batch(self) -> list[MarketSignalCandidate]:
        pending_tags = self._tag_repo.find_pending_graph()
        candidates = []
        for tag in pending_tags:
            candidate = self._evaluate(tag)
            candidates.append(candidate)

            if candidate.is_graph_eligible:
                self._write_to_stores(candidate)
                self._news_repo.update_graph_status(tag.article_id, GraphStatus.QUEUED)
            else:
                reason = GraphExcludeReason(candidate.ineligible_reason or "not_relevant")
                self._news_repo.update_graph_status(tag.article_id, GraphStatus.EXCLUDED, reason)

        return candidates

    def _evaluate(self, tag) -> MarketSignalCandidate:
        if tag.applicability in self._INELIGIBLE_APPLICABILITIES:
            return MarketSignalCandidate(
                article_id=tag.article_id, tag=tag, is_graph_eligible=False,
                ineligible_reason=GraphExcludeReason.NOT_RELEVANT,
            )
        if tag.confidence < self._min_confidence:
            return MarketSignalCandidate(
                article_id=tag.article_id, tag=tag, is_graph_eligible=False,
                ineligible_reason=GraphExcludeReason.LOW_CONFIDENCE,
            )
        if not tag.signal_type or not tag.event_type:
            return MarketSignalCandidate(
                article_id=tag.article_id, tag=tag, is_graph_eligible=False,
                ineligible_reason=GraphExcludeReason.MISSING_REQUIRED_FIELD,
            )
        return MarketSignalCandidate(article_id=tag.article_id, tag=tag, is_graph_eligible=True)

    def _write_to_stores(self, candidate: MarketSignalCandidate) -> None:
        tag = candidate.tag
        signal_dict = {
            "article_id": tag.article_id,
            "asset_family": tag.asset_family,
            "asset_class": tag.asset_class,
            "signal_type": tag.signal_type,
            "influence_direction": tag.influence_direction,
            "influence_strength": tag.influence_strength,
            "influence_period": tag.influence_period,
            "applicability": tag.applicability,
            "applied_scope": tag.applied_scope,
            "affected_evaluation_factors": tag.affected_evaluation_factors,
            "confidence": tag.confidence,
            "summary": tag.summary,
            "tagged_at": tag.tagged_at.isoformat(),
        }
        signal_id = self._signal_store.upsert(signal_dict)

        node = GraphNode(
            label="MarketSignal",
            properties={**signal_dict, "signal_id": signal_id},
            unique_key="signal_id",
        )
        self._graph_writer.upsert_node(node)
