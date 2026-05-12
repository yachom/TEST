"""VworldAdapter 단위 테스트 — 실제 vworld 응답 fixture 기반."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.processors.ontology_mapper.adapters.vworld_adapter import VworldAdapter
from core.shared.infra.graph_writer import GraphNode, GraphRelation


_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "vworld_response_sample.json"


@pytest.fixture(scope="module")
def vworld_raw() -> dict:
    """lookup.py 가 만들어낸 실제 vworld 응답을 도구 출력 형태로 감싼 dict."""
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    subject = payload["subject"]
    return {
        "source_type": "vworld",
        "source_id": subject["identifiers"]["pnu"],
        "content": {
            "address": subject["address"]["input"],
            "identifiers": subject["identifiers"],
            **payload["vworld"],
        },
    }


def _by_label(items, label: str) -> list[GraphNode]:
    return [i for i in items if isinstance(i, GraphNode) and i.label == label]


def _relations(items, relation_type: str) -> list[GraphRelation]:
    return [i for i in items if isinstance(i, GraphRelation) and i.relation_type == relation_type]


def test_address_node_uses_input_address(vworld_raw):
    items = VworldAdapter().map(vworld_raw)
    addrs = _by_label(items, "Address")
    assert len(addrs) == 1
    assert addrs[0].properties["address"] == "서울 관악구 관악로28길 20"


def test_land_node_pulls_from_ledger(vworld_raw):
    items = VworldAdapter().map(vworld_raw)
    lands = _by_label(items, "Land")
    assert len(lands) == 1
    props = lands[0].properties
    assert props["pnu"] == "1162010100100210015"
    assert props["area_m2"] == 400.0
    assert props["land_category"] == "대"
    assert props["owner_type"] == "개인"
    assert props["owner_count"] == 2


def test_land_use_picks_latest_year(vworld_raw):
    items = VworldAdapter().map(vworld_raw)
    uses = _by_label(items, "LandUse")
    assert len(uses) == 1
    props = uses[0].properties
    assert props["name"] == "제2종일반주거지역"
    # fixture 의 land_characteristics 는 2013~ 시계열. 가장 최근 연도가 선택돼야 한다.
    assert int(props["stdr_year"]) >= 2013
    assert props["situation"] == "주상용"


def test_land_price_picks_latest_year(vworld_raw):
    items = VworldAdapter().map(vworld_raw)
    prices = _by_label(items, "LandPrice")
    assert len(prices) == 1
    # fixture 의 indvdLandPrices.field 에서 stdrYear 최댓값이 선택돼야 한다.
    rows = vworld_raw["content"]["official_land_price"]["indvdLandPrices"]["field"]
    expected_year = max(int(r["stdrYear"]) for r in rows)
    assert int(prices[0].properties["year"]) == expected_year
    assert prices[0].properties["price_per_m2"] is not None


def test_zone_restrictions_emit_one_node_per_zone(vworld_raw):
    items = VworldAdapter().map(vworld_raw)
    zones = _by_label(items, "ZoneRestriction")
    zone_names = {z.properties["name"] for z in zones}
    # fixture 는 대공방어협조구역, 교육환경보호구역, 도시지역, 과밀억제권역 등을 포함
    assert "도시지역" in zone_names
    assert "대공방어협조구역" in zone_names
    assert len(zones) >= 4


def test_relations_connect_land_to_attributes(vworld_raw):
    items = VworldAdapter().map(vworld_raw)
    pnu = "1162010100100210015"

    located = _relations(items, "LOCATED_AT")
    assert len(located) == 1
    assert located[0].to_key == pnu

    has_use = _relations(items, "HAS_USE")
    assert len(has_use) == 1
    assert has_use[0].from_key == pnu

    has_price = _relations(items, "HAS_PRICE")
    assert len(has_price) == 1
    assert has_price[0].from_key == pnu

    subject_to = _relations(items, "SUBJECT_TO")
    assert all(r.from_key == pnu for r in subject_to)
    assert len(subject_to) >= 4


def test_handles_empty_payload_gracefully():
    """일부 endpoint 응답이 비어있어도 어댑터가 깨지지 않는다."""
    minimal = {
        "source_type": "vworld",
        "source_id": "1162010100100210015",
        "content": {
            "address": "테스트 주소",
            "identifiers": {"pnu": "1162010100100210015"},
            "land_forest_ledger": {},
            "land_characteristics": {},
            "land_use": {},
            "official_land_price": {},
        },
    }
    items = VworldAdapter().map(minimal)
    assert _by_label(items, "Address")
    assert _by_label(items, "Land")
    assert not _by_label(items, "LandUse")
    assert not _by_label(items, "LandPrice")
    assert not _by_label(items, "ZoneRestriction")
