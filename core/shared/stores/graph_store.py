"""그래프 DB 저장소 — scope_id 기반 read/write 추상화.

POC: InMemoryGraphStore (휘발).
영구 백엔드(Neo4j 등)는 같은 ABC 구현체 추가만으로 확장.

기존 GraphWriter (core/shared/infra/graph_writer.py) 는 배치 적재용으로 유지하고,
신규 에이전트/보고서 코드는 GraphStore 를 사용한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field

from core.shared.infra.graph_writer import GraphNode, GraphRelation


@dataclass
class Subgraph:
    """scope 단위 노드/엣지 묶음."""
    scope_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    relations: list[GraphRelation] = field(default_factory=list)


class GraphStore(ABC):
    """scope_id 로 격리된 그래프 저장/조회 인터페이스.

    scope_id 의미:
      - 휘발(POC): "analysis_<uuid>" — 분석 세션 단위, 종료 시 drop
      - 영구(향후): "asset_<id>" 또는 "region_<code>" — 누적 그래프

    구현체는 scope_id 를 격리 단위로 다루어야 한다.
    """

    @abstractmethod
    def upsert_node(self, scope_id: str, node: GraphNode) -> str:
        ...

    @abstractmethod
    def upsert_relation(self, scope_id: str, relation: GraphRelation) -> None:
        ...

    @abstractmethod
    def query_subgraph(self, scope_id: str) -> Subgraph:
        ...

    @abstractmethod
    def find_nodes(self, scope_id: str, label: str) -> list[GraphNode]:
        ...

    @abstractmethod
    def drop_scope(self, scope_id: str) -> None:
        ...


class InMemoryGraphStore(GraphStore):
    """POC 용 휘발성 In-Memory 구현체."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, GraphNode]] = defaultdict(dict)
        self._relations: dict[str, list[GraphRelation]] = defaultdict(list)

    def upsert_node(self, scope_id: str, node: GraphNode) -> str:
        key = self._node_key(node)
        self._nodes[scope_id][key] = node
        return key

    def upsert_relation(self, scope_id: str, relation: GraphRelation) -> None:
        self._relations[scope_id].append(relation)

    def query_subgraph(self, scope_id: str) -> Subgraph:
        return Subgraph(
            scope_id=scope_id,
            nodes=list(self._nodes.get(scope_id, {}).values()),
            relations=list(self._relations.get(scope_id, [])),
        )

    def find_nodes(self, scope_id: str, label: str) -> list[GraphNode]:
        return [n for n in self._nodes.get(scope_id, {}).values() if n.label == label]

    def drop_scope(self, scope_id: str) -> None:
        self._nodes.pop(scope_id, None)
        self._relations.pop(scope_id, None)

    @staticmethod
    def _node_key(node: GraphNode) -> str:
        unique_value = node.properties.get(node.unique_key, "")
        return f"{node.label}:{unique_value}"
