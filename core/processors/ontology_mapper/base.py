"""OntologyMapper — 수집물을 그래프 노드/엣지로 매핑.

어댑터 등록된 입력은 (가) 직접 매핑, 미등록 입력은 (다) LLM fallback.
상세 정책: docs/ONTOLOGY.md.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union

from core.shared.infra.graph_writer import GraphNode, GraphRelation

if TYPE_CHECKING:
    from core.processors.ontology_mapper.llm_fallback import LLMFallbackMapper


GraphItem = Union[GraphNode, GraphRelation]


class BaseAdapter(ABC):
    """구조화된 도구 응답을 직접 그래프 아이템으로 변환."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        ...

    @abstractmethod
    def map(self, raw: dict) -> list[GraphItem]:
        ...


class OntologyMapper:
    """어댑터 레지스트리 + LLM fallback."""

    def __init__(
        self,
        registry: dict[str, BaseAdapter],
        llm_fallback: "LLMFallbackMapper",
    ) -> None:
        self._registry = registry
        self._llm_fallback = llm_fallback

    def map(self, raw: dict) -> list[GraphItem]:
        source_type = raw.get("source_type", "unknown")
        adapter = self._registry.get(source_type)
        if adapter is not None:
            return adapter.map(raw)
        return self._llm_fallback.map(raw)

    def map_all(self, raws: list[dict]) -> list[GraphItem]:
        items: list[GraphItem] = []
        for raw in raws:
            items.extend(self.map(raw))
        return items
