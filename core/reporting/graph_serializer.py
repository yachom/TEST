"""그래프 → LLM 친화 텍스트 직렬화.

ReportBuilder, QARetriever 가 공유. 어댑터(가)가 정형 노드로 매핑한 그래프를
LLM 이 읽을 수 있는 압축 텍스트로 변환한다.

설계:
  - 라벨별 그룹화 (Address, Land, LandUse, LandPrice, ZoneRestriction, ...)
  - 노드는 properties 한 줄 요약, 빈 값 제외
  - 같은 라벨이 너무 많으면(예: ZoneRestriction 9개) head N + 합계 표시
  - 관계는 from -[type]-> to 화살표 형식
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from core.shared.stores.graph_store import Subgraph


_DEFAULT_MAX_NODES_PER_LABEL = 5
_DEFAULT_MAX_RELATIONS = 30


def serialize_subgraph_for_llm(
    subgraph: Subgraph,
    *,
    include_labels: Optional[list[str]] = None,
    max_nodes_per_label: int = _DEFAULT_MAX_NODES_PER_LABEL,
    max_relations: int = _DEFAULT_MAX_RELATIONS,
) -> str:
    """그래프를 LLM 입력용 텍스트로 변환.

    include_labels 가 주어지면 그 라벨만, 아니면 전부.
    """
    by_label: dict[str, list] = defaultdict(list)
    for node in subgraph.nodes:
        if include_labels and node.label not in include_labels:
            continue
        by_label[node.label].append(node)

    lines: list[str] = []
    if by_label:
        lines.append("## Nodes")
        for label in sorted(by_label.keys()):
            nodes = by_label[label]
            lines.append(f"{label} ({len(nodes)}):")
            for node in nodes[:max_nodes_per_label]:
                lines.append(f"  - {_format_node(node)}")
            if len(nodes) > max_nodes_per_label:
                lines.append(f"  ... ({len(nodes) - max_nodes_per_label} more)")

    if subgraph.relations:
        if lines:
            lines.append("")
        lines.append("## Relations")
        for rel in subgraph.relations[:max_relations]:
            lines.append(
                f"{rel.from_label}({rel.from_key}) -[{rel.relation_type}]-> "
                f"{rel.to_label}({rel.to_key})"
            )
        if len(subgraph.relations) > max_relations:
            lines.append(f"... ({len(subgraph.relations) - max_relations} more relations)")

    return "\n".join(lines) if lines else "(empty graph)"


def _format_node(node) -> str:
    """노드를 'unique_value | k=v k=v' 형태 한 줄로."""
    primary = node.properties.get(node.unique_key, "")
    extras = []
    for key, value in node.properties.items():
        if key == node.unique_key:
            continue
        if _is_empty(value):
            continue
        extras.append(f"{key}={_compact(value)}")
    if extras:
        return f"{primary} | {' '.join(extras)}"
    return str(primary)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _compact(value: Any) -> str:
    """리스트/dict 는 짧게. 너무 긴 문자열은 자른다."""
    if isinstance(value, list):
        return "[" + ",".join(str(v) for v in value[:5]) + ("..." if len(value) > 5 else "") + "]"
    text = str(value)
    if len(text) > 80:
        return text[:77] + "..."
    return text
