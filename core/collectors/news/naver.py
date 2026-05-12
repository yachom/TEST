"""네이버 뉴스 검색 API Provider — ApiKeyRotator 로 다중 키 fallback 지원.

네이버 quota 소진 신호: HTTP 429 (Too Many Requests), 또는 일부 응답에서 401/403.
키 1개로도 동작하나, 여러 (client_id, client_secret) 쌍을 주면 첫 키 소진 시
자동으로 다음 키로 영구 전환.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from core.collectors.news.base import NewsSearchProvider
from core.collectors.news.models import SearchQuery
from core.shared.infra.api_key_rotator import (
    AllKeysExhaustedError,
    ApiKeyRotator,
    status_code_predicate,
)


_BASE_URL = "https://openapi.naver.com/v1/search/news.json"
_TIMEOUT = 20

# 네이버가 quota / 인증 한도 도달 시 반환하는 코드.
# 401: 잘못된 키 / 만료, 403: 호출 제한, 429: rate limit.
_EXHAUSTED_STATUS_CODES = (401, 403, 429)


class NaverApiError(RuntimeError):
    pass


class NaverNewsSearchProvider(NewsSearchProvider):
    """네이버 뉴스 검색 API."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        credentials: list[tuple[str, str]] | None = None,
    ) -> None:
        if credentials is None:
            credentials = [(client_id, client_secret)] if client_id and client_secret else []
        if not credentials:
            raise ValueError("At least one (client_id, client_secret) credential is required")
        self._rotator: ApiKeyRotator[tuple[str, str], dict] = ApiKeyRotator(
            api_keys=credentials,
            is_exhausted=status_code_predicate(*_EXHAUSTED_STATUS_CODES),
        )

    def provider_name(self) -> str:
        return "naver"

    def search(self, query: SearchQuery) -> list[dict]:
        params = {
            "query": query.text,
            "display": int(query.max_display or 10),
            "start": 1,
            "sort": query.sort or "date",
        }
        url = f"{_BASE_URL}?{urllib.parse.urlencode(params)}"

        try:
            response = self._rotator.call(lambda creds: _fetch(url, creds))
        except AllKeysExhaustedError as e:
            raise NaverApiError(
                f"All Naver API keys exhausted. Last response: {e.last_response}"
            ) from e

        if response["status_code"] != 200:
            raise NaverApiError(
                f"Naver API error {response['status_code']}: {response['body'][:300]}"
            )

        data = json.loads(response["body"])
        return data.get("items", [])


def _fetch(url: str, creds: tuple[str, str]) -> dict:
    """단일 키로 GET 호출 → {status_code, body} 반환.

    네트워크 에러는 예외로 그대로 전파 (rotator 가 다음 키로 넘어가지 않음 — 일시적 문제일 수 있어 호출자 책임).
    """
    client_id, client_secret = creds
    req = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "Accept": "application/json",
            "User-Agent": "fnpricing/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
            return {
                "status_code": response.status,
                "body": response.read().decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as e:
        return {
            "status_code": e.code,
            "body": e.read().decode("utf-8", errors="replace"),
        }
