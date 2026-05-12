"""TransactionTool 응답 → 그래프 노드/엣지 매핑.

매핑 정책 (POC):
  Transaction* — 마스킹 매칭된 거래 N건. masked 지번이라 정확한 PNU 매칭 불가 →
                 Land 와 LIKELY_AT 관계 (확률적 연결).
  RegistryReviewRequired — HITL 트리거 시 1개 추가. 안내 URL / 이유 보존.

엣지:
  Land  -LIKELY_AT-       Transaction*    (마스킹 후보)
  Land  -REQUIRES_REVIEW- RegistryReviewRequired
"""
from __future__ import annotations

from typing import Any

from core.processors.ontology_mapper.base import BaseAdapter, GraphItem
from core.shared.infra.graph_writer import GraphNode, GraphRelation


class TransactionAdapter(BaseAdapter):
    @property
    def source_type(self) -> str:
        return "transaction"

    def map(self, raw: dict) -> list[GraphItem]:
        content = raw.get("content", {}) or {}
        identifiers = content.get("identifiers") or {}
        pnu = identifiers.get("pnu") or raw.get("source_id") or ""

        items: list[GraphItem] = []

        for idx, tx in enumerate(content.get("transactions") or []):
            tx_id = _transaction_id(pnu, tx, idx)
            items.append(GraphNode(
                label="Transaction",
                properties={
                    "id": tx_id,
                    "masked_lot": tx.get("지번"),
                    "building_type": tx.get("건물유형"),
                    "building_use": tx.get("건물주용도"),
                    "zoning": tx.get("용도지역"),
                    "floor": tx.get("층"),
                    "contract_year": tx.get("계약년도"),
                    "contract_month": tx.get("계약월"),
                    "contract_day": tx.get("계약일"),
                    "deal_amount_10k_krw": _to_int(tx.get("거래금액")),
                    "build_year": _to_int(tx.get("건축년도")),
                    "building_area_m2": _to_float(tx.get("건물면적")),
                    "land_area_m2": _to_float(tx.get("대지면적")),
                    "trade_type": tx.get("거래유형"),
                    "is_canceled": _yn(tx.get("해제여부")),
                },
                unique_key="id",
            ))
            if pnu:
                items.append(GraphRelation(
                    from_label="Land", from_key=pnu,
                    to_label="Transaction", to_key=tx_id,
                    relation_type="LIKELY_AT",
                    properties={"masked_lot": tx.get("지번")},
                ))

        review = content.get("registry_review") or {}
        if review.get("required") and pnu:
            review_id = f"{pnu}:registry_review"
            items.append(GraphNode(
                label="RegistryReviewRequired",
                properties={
                    "id": review_id,
                    "triggered_by": review.get("triggered_by"),
                    "total_masked_count": review.get("total_masked_count"),
                    "recent_12_months_count": review.get("recent_12_months_count"),
                    "guidance_url": review.get("guidance_url"),
                    "guidance_text": review.get("guidance_text"),
                },
                unique_key="id",
            ))
            items.append(GraphRelation(
                from_label="Land", from_key=pnu,
                to_label="RegistryReviewRequired", to_key=review_id,
                relation_type="REQUIRES_REVIEW",
            ))

        return items


def _transaction_id(pnu: str, tx: dict, idx: int) -> str:
    y = tx.get("계약년도", "")
    m = _zfill2(tx.get("계약월"))
    d = _zfill2(tx.get("계약일"))
    lot = str(tx.get("지번", "")).replace("*", "x")
    return f"{pnu}:tx:{y}-{m}-{d}:{lot}:{idx}"


def _zfill2(v: Any) -> str:
    if isinstance(v, int):
        return f"{v:02d}"
    return str(v or "")


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
    return s in {"O", "Y", "YES", "TRUE", "1"}
