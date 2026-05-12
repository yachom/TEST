"""ReportBuilder — 분석 그래프(Subgraph) 를 보고서로 변환.

LLM 에는 라벨 카운트가 아니라 직렬화된 노드/엣지 텍스트를 전달한다 —
어댑터가 정리한 정보가 실제로 보고서 summary 에 반영되도록.

Prompt + Schema: core.llm.PromptCatalog "reporting.report" 에서 로드.
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from core.reporting.graph_query_policy import GraphQueryPolicy
from core.reporting.graph_serializer import serialize_subgraph_for_llm

if TYPE_CHECKING:
    from core.llm.catalog import PromptCatalog
    from core.shared.infra.llm_client import LLMClient
    from core.shared.stores.graph_store import GraphStore


_PROMPT_KEY = "reporting.report"


class ReportBuilder:
    def __init__(
        self,
        graph_store: "GraphStore",
        llm_client: "LLMClient",
        prompt_catalog: "PromptCatalog",
        query_policy: GraphQueryPolicy | None = None,
    ) -> None:
        self._graph = graph_store
        self._llm = llm_client
        self._catalog = prompt_catalog
        self._policy = query_policy or GraphQueryPolicy()

    def build(self, scope_id: str) -> dict:
        subgraph = self._policy.filter(self._graph.query_subgraph(scope_id))
        labels = Counter(n.label for n in subgraph.nodes)
        rel_types = Counter(r.relation_type for r in subgraph.relations)
        graph_text = serialize_subgraph_for_llm(subgraph)

        rendered = self._catalog.render(_PROMPT_KEY, graph_text=graph_text)
        response = self._llm.call(rendered.to_llm_request())
        parsed = response.parsed or {}

        result = {
            "scope_id": scope_id,
            "node_count": len(subgraph.nodes),
            "relation_count": len(subgraph.relations),
            "nodes_by_label": dict(labels),
            "relations_by_type": dict(rel_types),
            "summary": parsed.get("summary") or _fallback_summary(labels, rel_types),
            "graph_text": graph_text,
            "prompt_version": rendered.version_hash,
        }

        review = _extract_registry_review(subgraph)
        if review is not None:
            result["registry_review"] = review

        return result


def _extract_registry_review(subgraph) -> dict | None:
    for node in subgraph.nodes:
        if node.label == "RegistryReviewRequired":
            return {
                "guidance_url": node.properties.get("guidance_url"),
                "guidance_text": node.properties.get("guidance_text"),
                "triggered_by": node.properties.get("triggered_by"),
                "total_masked_count": node.properties.get("total_masked_count"),
                "recent_12_months_count": node.properties.get("recent_12_months_count"),
            }
    return None


def _fallback_summary(labels: Counter, rel_types: Counter) -> str:
    return f"{sum(labels.values())}개 노드 / {sum(rel_types.values())}개 관계 식별됨."
