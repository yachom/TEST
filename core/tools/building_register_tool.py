"""건축물대장 도구 — 주소 받아 건축HUB 7 endpoint 호출 후 단일 dict 반환.

흐름: address → JusoClient → identifiers (lawd_cd, bjdong_cd, plat_gb_cd, bun, ji)
              → _BuildingRegisterClient × 7 → 응답 dict
              → source_type="building_register"

7 endpoint:
  basis              총괄표제부 / 일반건축물 기본
  title              표제부 (연면적 / 건폐율 / 용적률 / 구조)
  recap_title        총괄표제부 (집합건물용)
  exclusive_unit     전유공용면적 (집합건물 호별)
  exclusive_section  전유부 (집합건물)
  floor              층별 개요
  zone               지역지구 (vworld 와 어휘 공유 — LandUse 노드 자동 통합)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from core.tools.base import BaseTool
from core.tools.juso_client import JusoClient, JusoLookupError


_BR_BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService"
_TIMEOUT = 20


class BuildingRegisterError(RuntimeError):
    pass


class BuildingRegisterTool(BaseTool):
    @property
    def name(self) -> str:
        return "building_register_tool"

    @property
    def description(self) -> str:
        return (
            "주소를 받아 건축물대장 (일반건축물 / 집합건물) 의 표제부, 층별 개요, "
            "전유부, 지역지구 등을 수집한다."
        )

    def __init__(self, juso_key: str, molit_service_key: str) -> None:
        self._juso = JusoClient(juso_key)
        self._br = _BuildingRegisterClient(molit_service_key)

    def run(self, **kwargs) -> dict:
        address = kwargs.get("address", "")
        identifiers = self._juso.lookup(address)
        params = self._br.params_from_identifiers(identifiers)
        return {
            "source_type": "building_register",
            "source_id": identifiers["pnu"],
            "content": {
                "address": address,
                "identifiers": identifiers,
                "basis": self._br.get("getBrBasisOulnInfo", params),
                "title": self._br.get("getBrTitleInfo", params),
                "recap_title": self._br.get("getBrRecapTitleInfo", params),
                "exclusive_unit": self._br.get("getBrExposPubuseAreaInfo", params),
                "exclusive_section": self._br.get("getBrExposInfo", params),
                "floor": self._br.get("getBrFlrOulnInfo", params),
                "zone": self._br.get("getBrJijiguInfo", params),
            },
        }


class _BuildingRegisterClient:
    """건축HUB BldRgstHubService — PNU identifiers 기반 7 endpoint 호출."""

    def __init__(self, service_key: str, timeout: int = _TIMEOUT) -> None:
        if not service_key:
            raise ValueError("MOLIT service_key is required")
        self._key = urllib.parse.unquote(service_key)
        self._timeout = timeout

    def params_from_identifiers(self, identifiers: dict) -> dict:
        return {
            "sigunguCd": identifiers["lawd_cd"],
            "bjdongCd": identifiers["pnu"][5:10],
            "platGbCd": _plat_gb_cd(identifiers["land_type_code"]),
            "bun": identifiers["bun"],
            "ji": identifiers["ji"],
        }

    def get(self, endpoint: str, params: dict, num_of_rows: int = 20) -> dict:
        full_params = {
            "serviceKey": self._key,
            **params,
            "_type": "json",
            "numOfRows": num_of_rows,
            "pageNo": 1,
        }
        url = f"{_BR_BASE_URL}/{endpoint}?{urllib.parse.urlencode(full_params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "fnpricing/1.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise BuildingRegisterError(f"HTTP {e.code} from BldRgst {endpoint}: {detail}") from e
        except urllib.error.URLError as e:
            raise BuildingRegisterError(f"Network error from BldRgst {endpoint}: {e.reason}") from e
        return json.loads(body)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _plat_gb_cd(land_type_code: str) -> str:
    """PNU 의 land_type_code (1=대지, 2=산) → BldRgst 의 platGbCd (0=일반, 1=산)."""
    if land_type_code == "1":
        return "0"
    if land_type_code == "2":
        return "1"
    return land_type_code
