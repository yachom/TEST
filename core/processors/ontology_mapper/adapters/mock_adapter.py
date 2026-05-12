"""POC 용 Mock 어댑터 — MockAddressInfoTool 응답을 그래프로 매핑."""
from __future__ import annotations

from core.processors.ontology_mapper.base import BaseAdapter, GraphItem
from core.shared.infra.graph_writer import GraphNode, GraphRelation


class MockAddressAdapter(BaseAdapter):
    @property
    def source_type(self) -> str:
        return "mock_address"

    def map(self, raw: dict) -> list[GraphItem]:
        content = raw.get("content", {})
        address = content.get("address", "unknown")
        land_use = content.get("land_use", "unknown")

        items: list[GraphItem] = [
            GraphNode(
                label="Address",
                properties={"id": address, "address": address},
                unique_key="id",
            ),
            GraphNode(
                label="LandUse",
                properties={"id": land_use, "code": land_use},
                unique_key="id",
            ),
            GraphRelation(
                from_label="Address",
                from_key=address,
                to_label="LandUse",
                to_key=land_use,
                relation_type="HAS_USE",
            ),
        ]
        return items
