"""행정안전부 도로명주소 API 클라이언트 — 주소 텍스트 → PNU + identifiers.

여러 도구 (vworld, transaction, building_register) 가 공유. LLM 에 직접 노출되지 않으며
도구 내부에서만 사용한다.

반환 dict 키:
  pnu              19 자리 토지고유번호
  bjdong_code      10 자리 법정동코드 (PNU 의 앞 10자리)
  lawd_cd          5 자리 시군구코드 (PNU 의 앞 5자리)
  land_type_code   1 자리 (1=대지, 2=산)
  bun, ji          본번 / 부번 (각 4 자리 zero-padded)
  road_address     도로명주소 텍스트
  jibun_address    지번주소 텍스트
  emd_name         읍/면/동 명
  raw              Juso API 의 원본 row (디버깅용)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


_BASE_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
_TIMEOUT = 20


class JusoLookupError(RuntimeError):
    """Juso API 호출 실패 또는 매칭 결과 없음."""


class JusoClient:
    def __init__(self, confirm_key: str, timeout: int = _TIMEOUT) -> None:
        if not confirm_key:
            raise ValueError("JUSO confirm_key is required")
        self._key = confirm_key
        self._timeout = timeout

    def lookup(self, address: str) -> dict:
        params = {
            "confmKey": self._key,
            "currentPage": 1,
            "countPerPage": 5,
            "keyword": address,
            "resultType": "json",
        }
        request_url = f"{_BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            request_url,
            headers={"User-Agent": "fnpricing/1.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise JusoLookupError(f"HTTP {e.code} from Juso API: {detail}") from e
        except urllib.error.URLError as e:
            raise JusoLookupError(f"Network error from Juso API: {e.reason}") from e

        data = json.loads(body)
        rows = data.get("results", {}).get("juso") or []
        if not rows:
            raise JusoLookupError(f"No address match: {address!r}")
        selected = rows[0]
        pnu = build_pnu(
            selected.get("admCd", ""),
            "2" if str(selected.get("mtYn", "0")) == "1" else "1",
            selected.get("lnbrMnnm", "0"),
            selected.get("lnbrSlno", "0"),
        )
        return {
            "pnu": pnu,
            "bjdong_code": pnu[:10],
            "lawd_cd": pnu[:5],
            "land_type_code": pnu[10],
            "bun": pnu[11:15],
            "ji": pnu[15:19],
            "road_address": selected.get("roadAddr", ""),
            "jibun_address": selected.get("jibunAddr", ""),
            "emd_name": selected.get("emdNm", ""),
            "raw": selected,
        }


def build_pnu(bjdong_code: str, land_type_code: str, main: Any, sub: Any = "0") -> str:
    """PNU 19자리 합성. zfill 으로 4 자리 본번/부번 생성."""
    main4 = str(main or "0").strip().zfill(4)
    sub4 = str(sub or "0").strip().zfill(4)
    return f"{str(bjdong_code).strip()[:10]}{land_type_code}{main4}{sub4}"
