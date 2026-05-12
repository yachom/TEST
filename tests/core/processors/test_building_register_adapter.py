"""BuildingRegisterAdapter 단위 테스트 — 실제 응답 fixture 기반."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.processors.ontology_mapper.adapters.building_register_adapter import (
    BuildingRegisterAdapter,
)
from core.shared.infra.graph_writer import GraphNode, GraphRelation


_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "building_register_response_sample.json"


@pytest.fixture(scope="module")
def br_raw() -> dict:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    subject = payload["subject"]
    return {
        "source_type": "building_register",
        "source_id": subject["identifiers"]["pnu"],
        "content": {
            "address": subject["address"]["input"],
            "identifiers": subject["identifiers"],
            **payload["building_register"],
        },
    }


def _by_label(items, label: str) -> list[GraphNode]:
    return [i for i in items if isinstance(i, GraphNode) and i.label == label]


def _relations(items, relation_type: str) -> list[GraphRelation]:
    return [i for i in items if isinstance(i, GraphRelation) and i.relation_type == relation_type]


def test_building_node_pulls_title_metrics(br_raw):
    items = BuildingRegisterAdapter().map(br_raw)
    bldgs = _by_label(items, "Building")
    assert len(bldgs) == 1
    props = bldgs[0].properties
    assert props["plat_area_m2"] == 400.0
    assert props["total_area_m2"] == 718.25
    assert props["bc_ratio_pct"] == 55.13
    assert props["vl_ratio_pct"] == 150.72
    assert props["structure"] == "철근콘크리트구조"
    assert props["reg_kind"] == "일반건축물"


def test_floor_nodes_emitted(br_raw):
    items = BuildingRegisterAdapter().map(br_raw)
    floors = _by_label(items, "Floor")
    assert len(floors) >= 1
    purposes = {f.properties.get("main_purpose") for f in floors}
    assert "소매점" in purposes


def test_landuse_node_uses_zone_name(br_raw):
    items = BuildingRegisterAdapter().map(br_raw)
    uses = _by_label(items, "LandUse")
    assert len(uses) == 1
    assert uses[0].properties["name"] == "제2종일반주거지역"


def test_relations_link_land_building_floor_landuse(br_raw):
    items = BuildingRegisterAdapter().map(br_raw)
    pnu = "1162010100100210015"

    has_building = _relations(items, "HAS_BUILDING")
    assert len(has_building) == 1
    assert has_building[0].from_key == pnu

    has_floor = _relations(items, "HAS_FLOOR")
    assert len(has_floor) >= 1
    assert all(r.from_label == "Building" for r in has_floor)

    zoned_as = _relations(items, "ZONED_AS")
    assert len(zoned_as) == 1
    assert zoned_as[0].to_label == "LandUse"


def test_handles_empty_building_register():
    minimal = {
        "source_type": "building_register",
        "source_id": "1162010100100210015",
        "content": {
            "address": "테스트",
            "identifiers": {"pnu": "1162010100100210015"},
            "basis": {"response": {"body": {"items": {"item": []}}}},
            "title": {"response": {"body": {"items": {"item": []}}}},
            "floor": {"response": {"body": {"items": {"item": []}}}},
            "zone": {"response": {"body": {"items": {"item": []}}}},
        },
    }
    items = BuildingRegisterAdapter().map(minimal)
    assert items == []
