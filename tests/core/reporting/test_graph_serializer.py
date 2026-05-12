"""graph_serializer 단위 테스트."""
from __future__ import annotations

from core.reporting.graph_serializer import serialize_subgraph_for_llm
from core.shared.infra.graph_writer import GraphNode, GraphRelation
from core.shared.stores.graph_store import Subgraph


def _node(label: str, key: str, **props) -> GraphNode:
    return GraphNode(label=label, properties={"id": key, **props}, unique_key="id")


def _rel(from_label: str, from_key: str, to_label: str, to_key: str, t: str) -> GraphRelation:
    return GraphRelation(
        from_label=from_label, from_key=from_key,
        to_label=to_label, to_key=to_key, relation_type=t,
    )


def test_empty_subgraph():
    text = serialize_subgraph_for_llm(Subgraph(scope_id="s1"))
    assert text == "(empty graph)"


def test_groups_nodes_by_label_and_lists_props():
    sg = Subgraph(
        scope_id="s1",
        nodes=[
            _node("Address", "서울 관악구 관악로28길 20", address="서울 관악구 관악로28길 20"),
            _node("Land", "1162010100100210015", pnu="1162010100100210015", area_m2=400.0, land_category="대"),
            _node("LandUse", "제2종일반주거지역", name="제2종일반주거지역", situation="주상용"),
        ],
    )
    text = serialize_subgraph_for_llm(sg)

    assert "## Nodes" in text
    assert "Address (1)" in text
    assert "Land (1)" in text
    assert "area_m2=400.0" in text
    assert "land_category=대" in text
    assert "situation=주상용" in text


def test_skips_empty_property_values():
    sg = Subgraph(
        scope_id="s1",
        nodes=[_node("Land", "p1", area_m2=None, land_category="", owner_count=0, ld_name="서울")],
    )
    text = serialize_subgraph_for_llm(sg)
    assert "area_m2" not in text
    assert "land_category" not in text
    # 0 은 의미 있는 값이므로 포함
    assert "owner_count=0" in text
    assert "ld_name=서울" in text


def test_truncates_when_label_has_many_nodes():
    nodes = [_node("ZoneRestriction", f"Z{i:03d}", name=f"Zone {i}") for i in range(9)]
    sg = Subgraph(scope_id="s1", nodes=nodes)
    text = serialize_subgraph_for_llm(sg, max_nodes_per_label=3)

    assert "ZoneRestriction (9)" in text
    assert "Z000" in text
    assert "Z002" in text
    assert "Z008" not in text
    assert "(6 more)" in text


def test_serializes_relations():
    sg = Subgraph(
        scope_id="s1",
        nodes=[],
        relations=[
            _rel("Address", "addr1", "Land", "p1", "LOCATED_AT"),
            _rel("Land", "p1", "LandUse", "u1", "HAS_USE"),
        ],
    )
    text = serialize_subgraph_for_llm(sg)
    assert "## Relations" in text
    assert "Address(addr1) -[LOCATED_AT]-> Land(p1)" in text
    assert "Land(p1) -[HAS_USE]-> LandUse(u1)" in text


def test_include_labels_filter():
    sg = Subgraph(
        scope_id="s1",
        nodes=[
            _node("Land", "p1", area_m2=400),
            _node("ZoneRestriction", "Z1", name="도시지역"),
        ],
    )
    text = serialize_subgraph_for_llm(sg, include_labels=["Land"])
    assert "Land (1)" in text
    assert "ZoneRestriction" not in text


def test_compacts_long_string_property():
    long_value = "x" * 200
    sg = Subgraph(scope_id="s1", nodes=[_node("Land", "p1", note=long_value)])
    text = serialize_subgraph_for_llm(sg)
    assert "..." in text
    assert long_value not in text
