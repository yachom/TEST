"""건축물대장 응답 → 그래프 매핑.

매핑 정책 (POC):
  Building   건물 (basis + title 통합 — 연면적/건폐율/용적률/구조 등)
  Floor*     층별 개요 (지하/지상 N층)
  LandUse    지역지구 (vworld 와 같은 어휘 → 동일 노드로 자동 통합)

엣지:
  Land     -HAS_BUILDING-> Building
  Building -HAS_FLOOR->    Floor
  Building -ZONED_AS->     LandUse
"""
from __future__ import annotations

from typing import Any, Optional

from core.processors.ontology_mapper.base import BaseAdapter, GraphItem
from core.shared.infra.graph_writer import GraphNode, GraphRelation


class BuildingRegisterAdapter(BaseAdapter):
    @property
    def source_type(self) -> str:
        return "building_register"

    def map(self, raw: dict) -> list[GraphItem]:
        content = raw.get("content", {}) or {}
        identifiers = content.get("identifiers") or {}
        pnu = identifiers.get("pnu") or raw.get("source_id") or ""

        items: list[GraphItem] = []

        basis_item = _first(content.get("basis"))
        title_item = _first(content.get("title"))
        building_id = _building_id(basis_item, title_item)

        if building_id:
            items.append(GraphNode(
                label="Building",
                properties=_building_props(building_id, basis_item, title_item),
                unique_key="id",
            ))
            if pnu:
                items.append(GraphRelation(
                    from_label="Land", from_key=pnu,
                    to_label="Building", to_key=building_id,
                    relation_type="HAS_BUILDING",
                ))

            seen_floors: set[str] = set()
            for row in _items(content.get("floor")):
                floor_id = _floor_id(building_id, row)
                if not floor_id or floor_id in seen_floors:
                    continue
                seen_floors.add(floor_id)
                items.append(GraphNode(
                    label="Floor",
                    properties=_floor_props(floor_id, row),
                    unique_key="id",
                ))
                items.append(GraphRelation(
                    from_label="Building", from_key=building_id,
                    to_label="Floor", to_key=floor_id,
                    relation_type="HAS_FLOOR",
                ))

            seen_zones: set[str] = set()
            for zone_row in _items(content.get("zone")):
                zone_name = (zone_row.get("jijiguCdNm") or "").strip()
                if not zone_name or zone_name in seen_zones:
                    continue
                seen_zones.add(zone_name)
                items.append(GraphNode(
                    label="LandUse",
                    properties={
                        "id": zone_name,
                        "code": zone_row.get("jijiguCd"),
                        "name": zone_name,
                        "is_representative": _yn(zone_row.get("reprYn")),
                    },
                    unique_key="id",
                ))
                items.append(GraphRelation(
                    from_label="Building", from_key=building_id,
                    to_label="LandUse", to_key=zone_name,
                    relation_type="ZONED_AS",
                ))

        return items


# ---------------------------------------------------------------------------
# 응답 파싱 헬퍼
# ---------------------------------------------------------------------------


def _items(payload: Any) -> list[dict]:
    """건축HUB 의 nested response.body.items.item 리스트화."""
    if not isinstance(payload, dict):
        return []
    body = (payload.get("response", {}) or {}).get("body", {}) or {}
    items_root = body.get("items") or {}
    item = items_root.get("item") if isinstance(items_root, dict) else None
    if isinstance(item, list):
        return item
    if isinstance(item, dict):
        return [item]
    return []


def _first(payload: Any) -> Optional[dict]:
    items = _items(payload)
    return items[0] if items else None


def _building_id(basis: Optional[dict], title: Optional[dict]) -> str:
    src = basis or title or {}
    bldg_id = src.get("bldgId") or src.get("mgmBldrgstPk")
    return str(bldg_id) if bldg_id else ""


def _floor_id(building_id: str, row: dict) -> str:
    flr_gb = row.get("flrGbCd")
    flr_no = row.get("flrNo")
    if flr_gb is None or flr_no is None:
        return ""
    return f"{building_id}:floor:{flr_gb}-{flr_no}"


def _building_props(building_id: str, basis: Optional[dict], title: Optional[dict]) -> dict:
    basis = basis or {}
    title = title or {}
    bldg_name = (basis.get("bldNm") or title.get("bldNm") or "").strip()
    return {
        "id": building_id,
        "name": bldg_name or None,
        "reg_kind": basis.get("regstrKindCdNm"),
        "address": basis.get("newPlatPlc") or basis.get("platPlc"),
        "plat_area_m2": _to_float(title.get("platArea")),
        "arch_area_m2": _to_float(title.get("archArea")),
        "total_area_m2": _to_float(title.get("totArea")),
        "bc_ratio_pct": _to_float(title.get("bcRat")),
        "vl_ratio_pct": _to_float(title.get("vlRat")),
        "structure": title.get("strctCdNm"),
        "creation_date": basis.get("crtnDay"),
    }


def _floor_props(floor_id: str, row: dict) -> dict:
    return {
        "id": floor_id,
        "floor_kind": row.get("flrGbCdNm"),
        "floor_no": _to_int(row.get("flrNo")),
        "main_purpose": row.get("mainPurpsCdNm"),
        "etc_purpose": row.get("etcPurps"),
        "structure": row.get("strctCdNm"),
        "area_m2": _to_float(row.get("area")),
    }


def _to_int(v: Any):
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v: Any):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _yn(v: Any) -> bool:
    s = str(v or "").strip().upper()
    return s in {"Y", "1", "TRUE", "YES"}
