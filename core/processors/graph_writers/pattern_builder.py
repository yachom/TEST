"""GraphPatternBuilder — OntologyTag 를 그래프 노드/엣지 패턴으로 변환.

매핑 정책 변경 시 본 파일만 수정. POC 는 단순한 1 노드 매핑.
추후 신호 → 평가요인/지역/기간 등 다중 엣지로 정교화.
"""
from __future__ import annotations

from typing import Union

from core.processors.taggers.models import OntologyTag
from core.shared.infra.graph_writer import GraphNode, GraphRelation


GraphItem = Union[GraphNode, GraphRelation]


class GraphPatternBuilder:
    def build(self, tag: OntologyTag) -> list[GraphItem]:
        signal_id = tag.article_id or (tag.summary[:40] if tag.summary else "unknown")
        items: list[GraphItem] = [
            GraphNode(
                label="MarketSignal",
                properties={
                    "id": signal_id,
                    "summary": tag.summary,
                    "signal_type": _enum_value(tag.signal_type),
                    "direction": _enum_value(tag.influence_direction),
                    "strength": _enum_value(tag.influence_strength),
                    "confidence": tag.confidence,
                },
                unique_key="id",
            )
        ]
        for factor in tag.affected_evaluation_factors:
            items.append(GraphNode(
                label="EvaluationFactor",
                properties={"id": factor, "name": factor},
                unique_key="id",
            ))
            items.append(GraphRelation(
                from_label="MarketSignal",
                from_key=signal_id,
                to_label="EvaluationFactor",
                to_key=factor,
                relation_type="AFFECTS",
            ))
        return items


def _enum_value(value) -> str:
    if value is None:
        return ""
    return getattr(value, "value", str(value))
