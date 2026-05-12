from __future__ import annotations

import uuid
from typing import Optional

from core.shared.stores.report_store import ReportStore


class InMemoryReportStore(ReportStore):
    """테스트 / POC 용 인메모리 보고서 저장소.

    address_key 별 최신 보고서만 빠르게 조회할 수 있도록 인덱스를 함께 둔다.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, dict] = {}
        self._latest_by_address: dict[str, str] = {}
        self._latest_by_scope: dict[str, str] = {}

    def save(self, address_key: str, report_package: dict) -> str:
        report_id = report_package.get("id") or f"report_{uuid.uuid4().hex[:12]}"
        record = {**report_package, "id": report_id, "address_key": address_key}
        self._by_id[report_id] = record
        self._latest_by_address[address_key] = report_id
        scope_id = record.get("scope_id")
        if scope_id:
            self._latest_by_scope[scope_id] = report_id
        return report_id

    def get(self, report_id: str) -> Optional[dict]:
        return self._by_id.get(report_id)

    def find_latest_by_address(self, address_key: str) -> Optional[dict]:
        report_id = self._latest_by_address.get(address_key)
        return self._by_id.get(report_id) if report_id else None

    def get_latest(self, scope_id: str) -> Optional[dict]:
        """QARetriever 가 사용하는 scope_id 기반 조회."""
        report_id = self._latest_by_scope.get(scope_id)
        return self._by_id.get(report_id) if report_id else None
