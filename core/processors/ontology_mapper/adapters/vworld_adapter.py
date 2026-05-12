"""vworld 응답 → 그래프 노드/엣지 매핑 어댑터.

매핑 정책 (POC):
  Address       — 입력 주소 텍스트
  Land          — PNU 식별, 면적/지목/소유 (토지대장)
  LandUse       — 가장 최근 land_characteristics 의 용도지역
  LandPrice     — 가장 최근 개별공시지가 (연도 + 단가)
  ZoneRestriction* — 모든 용도지역지구 지정 (대공방어협조구역, 도시지역 등)

엣지:
  Address  -LOCATED_AT-> Land
  Land     -HAS_USE-> LandUse
  Land     -HAS_PRICE-> LandPrice
  Land     -SUBJECT_TO-> ZoneRestriction
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from core.processors.ontology_mapper.base import BaseAdapter, GraphItem
from core.shared.infra.graph_writer import GraphNode, GraphRelation


class VworldAdapter(BaseAdapter):
    @property
    def source_type(self) -> str:
        return "vworld"

    def map(self, raw: dict) -> list[GraphItem]:
        content = raw.get("content", {}) or {}
        address = content.get("address") or ""
        identifiers = content.get("identifiers") or {}
        pnu = identifiers.get("pnu") or raw.get("source_id") or ""

        items: list[GraphItem] = []

        if address:
            items.append(GraphNode(
                label="Address",
                properties={"id": address, "address": address},
                unique_key="id",
            ))

        ledger = _first_ledger(content.get("land_forest_ledger"))
        latest_char = _latest_by_year(content.get("land_characteristics"), "landCharacteristicss")
        latest_price = _latest_by_year(content.get("official_land_price"), "indvdLandPrices")

        land_props: dict[str, Any] = {"id": pnu, "pnu": pnu}
        if ledger:
            land_props.update({
                "area_m2": _to_float(ledger.get("lndpclAr")),
                "land_category": ledger.get("lndcgrCodeNm"),
                "owner_type": ledger.get("posesnSeCodeNm"),
                "owner_count": _to_int(ledger.get("cnrsPsnCo")),
                "ld_code": ledger.get("ldCode"),
                "ld_name": ledger.get("ldCodeNm"),
                "lot_no": ledger.get("mnnmSlno"),
            })
        items.append(GraphNode(label="Land", properties=land_props, unique_key="id"))

        if address and pnu:
            items.append(GraphRelation(
                from_label="Address", from_key=address,
                to_label="Land", to_key=pnu,
                relation_type="LOCATED_AT",
            ))

        if latest_char:
            use_name = latest_char.get("prposArea1Nm") or "unknown"
            items.append(GraphNode(
                label="LandUse",
                properties={
                    "id": use_name,
                    "code": latest_char.get("prposArea1"),
                    "name": use_name,
                    "situation": latest_char.get("ladUseSittnNm"),
                    "topology": latest_char.get("tpgrphHgCodeNm"),
                    "shape": latest_char.get("tpgrphFrmCodeNm"),
                    "road_side": latest_char.get("roadSideCodeNm"),
                    "stdr_year": latest_char.get("stdrYear"),
                },
                unique_key="id",
            ))
            items.append(GraphRelation(
                from_label="Land", from_key=pnu,
                to_label="LandUse", to_key=use_name,
                relation_type="HAS_USE",
            ))

        if latest_price:
            year = str(latest_price.get("stdrYear", "")).strip()
            price_id = f"{pnu}:{year}" if year else pnu
            items.append(GraphNode(
                label="LandPrice",
                properties={
                    "id": price_id,
                    "pnu": pnu,
                    "year": year,
                    "price_per_m2": _to_int(latest_price.get("pblntfPclnd")),
                    "publish_date": latest_price.get("pblntfDe"),
                },
                unique_key="id",
            ))
            items.append(GraphRelation(
                from_label="Land", from_key=pnu,
                to_label="LandPrice", to_key=price_id,
                relation_type="HAS_PRICE",
            ))

        seen_zones: set[str] = set()
        for zone in _iter_zones(content.get("land_use")):
            zone_code = zone.get("prposAreaDstrcCode") or ""
            if not zone_code or zone_code in seen_zones:
                continue
            seen_zones.add(zone_code)
            zone_name = zone.get("prposAreaDstrcCodeNm") or zone_code
            items.append(GraphNode(
                label="ZoneRestriction",
                properties={
                    "id": zone_code,
                    "code": zone_code,
                    "name": zone_name,
                    "applicable": zone.get("cnflcAtNm"),
                },
                unique_key="id",
            ))
            items.append(GraphRelation(
                from_label="Land", from_key=pnu,
                to_label="ZoneRestriction", to_key=zone_code,
                relation_type="SUBJECT_TO",
            ))

        return items


# ---------------------------------------------------------------------------
# 응답 파싱 헬퍼
# ---------------------------------------------------------------------------

def _first_ledger(payload: Any) -> Optional[dict]:
    if not isinstance(payload, dict):
        return None
    rows = (payload.get("ladfrlVOList", {}) or {}).get("ladfrlVOList") or []
    return rows[0] if rows else None


def _latest_by_year(payload: Any, container_key: str) -> Optional[dict]:
    if not isinstance(payload, dict):
        return None
    rows = (payload.get(container_key, {}) or {}).get("field") or []
    if not rows:
        return None
    try:
        return max(rows, key=lambda r: int(r.get("stdrYear") or 0))
    except (TypeError, ValueError):
        return rows[-1]


def _iter_zones(payload: Any) -> Iterable[dict]:
    if not isinstance(payload, dict):
        return []
    return (payload.get("landUses", {}) or {}).get("field") or []


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
