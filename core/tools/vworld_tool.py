"""vworld 도구 — 주소 받아 토지 정보 4 개 endpoint 호출 후 단일 dict 반환.

내부 의존성:
  JusoClient    — core.tools.juso_client: 주소 → PNU + identifiers
  _VworldClient — vworld 토지 정보 API: PNU → 4 개 endpoint 응답

흐름: address → JusoClient.lookup() → PNU → _VworldClient.get() x 4
응답 형식은 OntologyMapper 의 VworldAdapter 와 짝을 맞춘다.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from core.tools.base import BaseTool
from core.tools.juso_client import JusoClient, JusoLookupError


_VWORLD_BASE_URL = "https://api.vworld.kr/ned/data"
_TIMEOUT = 20


class VworldLookupError(RuntimeError):
    """vworld API 호출 실패."""


class VworldTool(BaseTool):
    """LLM 에이전트가 호출하는 vworld 도구.

    address 입력 → 내부에서 Juso → vworld 4 endpoint 호출 → 단일 dict 반환.
    내부 client 는 캡슐화 — 호출 측은 키만 주입.
    """

    @property
    def name(self) -> str:
        return "vworld_tool"

    @property
    def description(self) -> str:
        return (
            "주소를 받아 토지대장, 토지특성(공시지가/용도지역/지목/지형), "
            "용도지역지구 지정, 개별공시지가 시계열을 수집한다."
        )

    def __init__(
        self,
        juso_key: str,
        vworld_key: str,
        vworld_domain: Optional[str] = None,
    ) -> None:
        self._juso = JusoClient(juso_key)
        self._vworld = _VworldClient(vworld_key, domain=vworld_domain)

    def run(self, **kwargs) -> dict:
        address = kwargs.get("address", "")
        identifiers = self._juso.lookup(address)
        pnu = identifiers["pnu"]
        return {
            "source_type": "vworld",
            "source_id": pnu,
            "content": {
                "address": address,
                "identifiers": identifiers,
                "land_forest_ledger": self._vworld.get(_VworldClient.LAND_FOREST_LEDGER, pnu),
                "land_characteristics": self._vworld.get(_VworldClient.LAND_CHARACTERISTICS, pnu),
                "land_use": self._vworld.get(_VworldClient.LAND_USE, pnu),
                "official_land_price": self._vworld.get(_VworldClient.OFFICIAL_LAND_PRICE, pnu),
            },
        }


class _VworldClient:
    """vworld 토지 정보 API — PNU 단위 4 개 endpoint."""

    LAND_FOREST_LEDGER = "ladfrlList"
    LAND_CHARACTERISTICS = "getLandCharacteristics"
    LAND_USE = "getLandUseAttr"
    OFFICIAL_LAND_PRICE = "getIndvdLandPriceAttr"

    def __init__(
        self,
        api_key: str,
        domain: Optional[str] = None,
        timeout: int = _TIMEOUT,
    ) -> None:
        if not api_key:
            raise ValueError("VWORLD api_key is required")
        self._key = api_key
        self._domain = domain
        self._timeout = timeout

    def get(self, endpoint: str, pnu: str, num_of_rows: int = 100) -> dict:
        params: dict[str, Any] = {
            "key": self._key,
            "pnu": pnu,
            "format": "json",
            "numOfRows": num_of_rows,
            "pageNo": 1,
        }
        if self._domain:
            params["domain"] = self._domain
        # vworld NED API는 등록 도메인을 Referer 헤더로 보내야 키 인증 통과
        extra_headers = {"Referer": f"http://{self._domain}"} if self._domain else {}
        body = _http_get_text(
            f"{_VWORLD_BASE_URL}/{endpoint}", params, self._timeout,
            error_cls=VworldLookupError, label=f"vworld {endpoint}",
            extra_headers=extra_headers,
        )
        return json.loads(body)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _http_get_text(
    url: str,
    params: dict[str, Any],
    timeout: int,
    *,
    error_cls: type[RuntimeError],
    label: str,
    extra_headers: dict[str, str] | None = None,
) -> str:
    request_url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "fnpricing/1.0", "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(request_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise error_cls(f"HTTP {e.code} from {label}: {detail}") from e
    except urllib.error.URLError as e:
        raise error_cls(f"Network error from {label}: {e.reason}") from e
