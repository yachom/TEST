"""실거래가 도구 — 주소 받아 PublicDataReader 로 시군구 단위 거래 조회 후
입력 주소의 본번 prefix 와 마스킹 매칭되는 거래만 필터링.

흐름:
  address → JusoClient.lookup() → identifiers (lawd_cd, bjdong_name, jibun)
        → _TransactionClient.fetch() → 시군구 거래 N건
        → _filter_by_dong_and_lot_mask() → 마스킹 매칭 거래만
        → HITL 트리거 판정 → 응답 dict (source_type="transaction")

마스킹: 실거래가 응답의 지번은 "21-1*", "8**" 같은 마스킹 형태.
입력 본번이 마스킹 prefix 와 매치되면 후보로 본다 (정확 매칭 불가능 — 등기로 확인).
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import date
from typing import Any, Optional

from core.tools.base import BaseTool
from core.tools.juso_client import JusoClient, JusoLookupError


_TIMEOUT = 20


class TransactionLookupError(RuntimeError):
    """실거래가 조회 실패."""


class TransactionTool(BaseTool):
    """LLM 에이전트가 호출하는 실거래가 도구.

    address 입력 → 마스킹 매칭 거래 + HITL 트리거 정보 반환.
    """

    @property
    def name(self) -> str:
        return "transaction_tool"

    @property
    def description(self) -> str:
        return (
            "주소를 받아 시군구 단위 실거래가 (상업업무용 매매) 를 조회하고, "
            "입력 주소의 본번과 마스킹 매칭되는 거래만 추린다. "
            "거래 건수 / 빈도가 임계 이상이면 등기사항증명서 PDF 업로드 안내 플래그를 설정한다."
        )

    def __init__(
        self,
        juso_key: str,
        molit_service_key: str,
        property_type: str = "상업업무용",
        trade_type: str = "매매",
        months: int = 12,
        registry_review_total_count: int = 20,
        registry_review_recent_12_months: int = 5,
        always_trigger_review: bool = False,
    ) -> None:
        self._juso = JusoClient(juso_key)
        self._tx = _TransactionClient(molit_service_key)
        self._property_type = property_type
        self._trade_type = trade_type
        self._months = months
        self._threshold_total = registry_review_total_count
        self._threshold_recent = registry_review_recent_12_months
        self._always_trigger = always_trigger_review

    def run(self, **kwargs) -> dict:
        address = kwargs.get("address", "")
        identifiers = self._juso.lookup(address)
        target_lot = _normalize_jibun(identifiers["bun"], identifiers["ji"])
        bjdong_name = identifiers.get("emd_name", "")

        start_ym, end_ym = _default_period(self._months)
        df = self._tx.fetch(
            sigungu_code=identifiers["lawd_cd"],
            property_type=self._property_type,
            trade_type=self._trade_type,
            start_year_month=start_ym,
            end_year_month=end_ym,
        )

        all_rows = _df_to_rows(df)
        dong_rows = _filter_by_dong(all_rows, bjdong_name)
        masked_rows = _filter_by_lot_mask(dong_rows, target_lot)

        review_decision = self._decide_registry_review(masked_rows)

        return {
            "source_type": "transaction",
            "source_id": identifiers["pnu"],
            "content": {
                "address": address,
                "identifiers": identifiers,
                "target_lot": target_lot,
                "query": {
                    "property_type": self._property_type,
                    "trade_type": self._trade_type,
                    "sigungu_code": identifiers["lawd_cd"],
                    "start_year_month": start_ym,
                    "end_year_month": end_ym,
                },
                "row_counts": {
                    "sigungu_total": len(all_rows),
                    "dong_filtered": len(dong_rows),
                    "lot_mask_filtered": len(masked_rows),
                },
                "transactions": masked_rows,
                "registry_review": review_decision,
            },
        }

    def _decide_registry_review(self, masked_rows: list[dict]) -> dict:
        total = len(masked_rows)
        recent_count = _count_recent_months(masked_rows, months=12)
        triggered_by = []
        if self._always_trigger:
            triggered_by.append("always_trigger")
        if total >= self._threshold_total:
            triggered_by.append(f"total_count>={self._threshold_total}")
        if recent_count >= self._threshold_recent:
            triggered_by.append(f"recent_12_months>={self._threshold_recent}")
        return {
            "required": bool(triggered_by),
            "triggered_by": triggered_by,
            "total_masked_count": total,
            "recent_12_months_count": recent_count,
            "guidance_url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000098&HighCtgCD=A02004002&tp_seq=01&Mcode=10205",
            "guidance_text": (
                "마스킹 처리된 실거래가만으로 정확한 권리관계/거래내역 식별이 어렵습니다. "
                "정부24 인터넷등기소에서 등기사항증명서를 발급받아 PDF 로 업로드하세요."
            ),
        }


# ---------------------------------------------------------------------------
# 내부 client
# ---------------------------------------------------------------------------


class _TransactionClient:
    """국토교통부 실거래가 — PublicDataReader 의 TransactionPrice 래퍼."""

    def __init__(self, service_key: str) -> None:
        if not service_key:
            raise ValueError("MOLIT service_key is required")
        # PublicDataReader 가 기대하는 형태로 unquote
        self._key = urllib.parse.unquote(service_key)

    def fetch(
        self,
        sigungu_code: str,
        property_type: str,
        trade_type: str,
        start_year_month: str,
        end_year_month: str,
    ):
        try:
            from PublicDataReader import TransactionPrice
        except ImportError as e:
            raise TransactionLookupError(
                "PublicDataReader is not installed. Run: pip install PublicDataReader"
            ) from e
        api = TransactionPrice(self._key)
        try:
            return api.get_data(
                property_type=property_type,
                trade_type=trade_type,
                sigungu_code=sigungu_code,
                start_year_month=start_year_month,
                end_year_month=end_year_month,
            )
        except Exception as e:
            raise TransactionLookupError(f"PublicDataReader error: {e}") from e


# ---------------------------------------------------------------------------
# 필터 / 헬퍼
# ---------------------------------------------------------------------------


def _df_to_rows(df) -> list[dict]:
    """pandas DataFrame → list[dict]. 비어있을 수 있음."""
    if df is None:
        return []
    rows_json = df.to_json(orient="records", force_ascii=False, date_format="iso")
    return json.loads(rows_json) if rows_json else []


def _filter_by_dong(rows: list[dict], bjdong_name: str) -> list[dict]:
    if not bjdong_name:
        return rows
    return [r for r in rows if str(r.get("법정동", "")).strip() == bjdong_name]


def _filter_by_lot_mask(rows: list[dict], target_lot: str) -> list[dict]:
    if not target_lot:
        return rows
    return [r for r in rows if _lot_mask_match(r.get("지번"), target_lot)]


def _lot_mask_match(candidate: Any, target_lot: str) -> bool:
    """마스킹 지번 매칭. lookup.py 의 lot_mask_match 와 동일 규칙.

    - candidate 에 * 없으면: 정확 일치
    - candidate 에 * 있으면: 본번(- 앞쪽) prefix 매칭
    - "*" 같은 전체 마스킹은 모두 통과
    """
    if candidate is None:
        return False
    candidate_text = str(candidate).strip()
    if not candidate_text:
        return False
    if "*" not in candidate_text:
        return candidate_text == target_lot

    target_main = target_lot.split("-", 1)[0]
    candidate_main = candidate_text.split("-", 1)[0]
    candidate_prefix = candidate_main.replace("*", "")
    if candidate_prefix == "":
        return True
    return target_main.startswith(candidate_prefix)


def _count_recent_months(rows: list[dict], months: int) -> int:
    """rows 중 contract date 가 최근 N 개월 내인 건수."""
    today = date.today()
    cutoff_year_month = (today.year * 12 + today.month - 1) - months
    count = 0
    for r in rows:
        y = r.get("계약년도")
        m = r.get("계약월")
        if y is None or m is None:
            continue
        try:
            ym_index = int(y) * 12 + int(m) - 1
        except (TypeError, ValueError):
            continue
        if ym_index >= cutoff_year_month:
            count += 1
    return count


def _default_period(months: int) -> tuple[str, str]:
    today = date.today()
    end_index = today.year * 12 + today.month - 2  # 한 달 전 (당월 데이터는 sparse)
    start_index = end_index - (months - 1)
    return _ym(start_index), _ym(end_index)


def _ym(month_index: int) -> str:
    return f"{month_index // 12:04d}{month_index % 12 + 1:02d}"


def _normalize_jibun(bun: str, ji: str) -> str:
    main_int = str(int(bun)) if str(bun).isdigit() else str(bun).lstrip("0") or "0"
    sub_int = str(int(ji)) if str(ji).isdigit() else str(ji).lstrip("0") or "0"
    return main_int if sub_int == "0" else f"{main_int}-{sub_int}"
