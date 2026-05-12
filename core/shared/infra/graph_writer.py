from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GraphNode:
    label: str
    properties: dict
    unique_key: str


@dataclass
class GraphRelation:
    from_label: str
    from_key: str
    to_label: str
    to_key: str
    relation_type: str
    properties: dict | None = None


class GraphWriter(ABC):
    @abstractmethod
    def upsert_node(self, node: GraphNode) -> str:
        ...

    @abstractmethod
    def upsert_relation(self, relation: GraphRelation) -> None:
        ...

    @abstractmethod
    def upsert_batch(self, nodes: list[GraphNode], relations: list[GraphRelation]) -> dict:
        ...


class NoOpGraphWriter(GraphWriter):
    """Graph DB 연동 전 사용하는 NoOp 구현체."""

    def upsert_node(self, node: GraphNode) -> str:
        return f"noop:{node.label}:{node.properties.get(node.unique_key, '')}"

    def upsert_relation(self, relation: GraphRelation) -> None:
        pass

    def upsert_batch(self, nodes: list[GraphNode], relations: list[GraphRelation]) -> dict:
        return {"nodes": len(nodes), "relations": len(relations), "backend": "noop"}
