"""GraphQueryPolicy — 그래프에서 어떤 부분을 보고서/QA 에 반영할지 정책.

POC: 모든 노드/엣지 포함. 추후 traversal 깊이, 필수 노드 라벨 등 정교화.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.shared.stores.graph_store import Subgraph


@dataclass
class GraphQueryPolicy:
    include_labels: list[str] = field(default_factory=list)   # 비어있으면 전부
    max_traversal_depth: int = 2

    def filter(self, subgraph: Subgraph) -> Subgraph:
        if not self.include_labels:
            return subgraph
        nodes = [n for n in subgraph.nodes if n.label in self.include_labels]
        return Subgraph(scope_id=subgraph.scope_id, nodes=nodes, relations=subgraph.relations)
