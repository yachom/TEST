"""POC 용 Mock 주소 정보 도구.

실제 vworld / 건축허브 / 상가 API 연동 전까지 사용.
출력 형식은 OntologyMapper 의 MockAddressAdapter 와 짝을 맞춘다.
"""
from __future__ import annotations

from core.tools.base import BaseTool


class MockAddressInfoTool(BaseTool):
    @property
    def name(self) -> str:
        return "mock_address_info_tool"

    @property
    def description(self) -> str:
        return "주소를 받아 가짜 부동산 공적 정보를 반환한다 (POC 용)."

    def run(self, **kwargs) -> dict:
        address = kwargs.get("address", "unknown")
        return {
            "source_type": "mock_address",
            "source_id": address,
            "content": {
                "address": address,
                "land_use": "제2종근린",
                "land_area_m2": 1500.0,
                "owner_count": 47,
            },
        }
