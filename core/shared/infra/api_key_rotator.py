"""API 키 로테이션 유틸 — quota 소진 시 다음 키로 자동 전환.

설계 원칙:
- 사전 quota 체크 없음. 호출하고 응답을 보고 판단한다.
- "quota 소진"의 신호는 API 마다 다르므로 호출자가 predicate 로 주입한다.
  - 네이버: HTTP 403/429
  - 구글 검색: 200 응답 안에 `error.code` 포함
  - 다른 API: 응답 헤더, body 의 특정 필드 등
- 한 번 소진된 키는 영구히 건너뛰고 다음 호출부터는 그 다음 키로 시작한다.
"""
from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

K = TypeVar("K")  # API 키 타입 (str, tuple[str, str], dict[str, str], ...)
R = TypeVar("R")  # 호출 함수의 응답 타입


class AllKeysExhaustedError(RuntimeError):
    """모든 API 키가 quota 소진된 상태."""

    def __init__(self, key_count: int, last_response: Any = None) -> None:
        super().__init__(f"All {key_count} API keys exhausted.")
        self.key_count = key_count
        self.last_response = last_response


class ApiKeyRotator(Generic[K, R]):
    """여러 API 키를 순회하며 quota 소진 시 다음 키로 자동 전환.

    사용 예 (네이버):
        rotator = ApiKeyRotator(
            api_keys=[(cid1, secret1), (cid2, secret2)],
            is_exhausted=status_code_predicate(403, 429),
        )
        response = rotator.call(lambda creds: httpx.get(url, headers=_headers(creds)))

    사용 예 (구글, body 의 errorCode 로 판단):
        def is_google_exhausted(resp):
            return resp.status_code == 200 and resp.json().get("error", {}).get("code") == 429
        rotator = ApiKeyRotator(api_keys=[k1, k2], is_exhausted=is_google_exhausted)
    """

    def __init__(
        self,
        api_keys: list[K],
        is_exhausted: Callable[[R], bool],
    ) -> None:
        if not api_keys:
            raise ValueError("api_keys must contain at least one key")
        self._keys: list[K] = list(api_keys)
        self._is_exhausted = is_exhausted
        self._current_index = 0

    def call(self, fn: Callable[[K], R]) -> R:
        """현재 키로 fn 을 호출. 응답이 quota 소진이면 다음 키로 영구 전환 후 재시도."""
        last_response: R | None = None
        while self._current_index < len(self._keys):
            key = self._keys[self._current_index]
            response = fn(key)
            if not self._is_exhausted(response):
                return response
            last_response = response
            self._current_index += 1
        raise AllKeysExhaustedError(len(self._keys), last_response)

    @property
    def current_key_index(self) -> int:
        """다음 call() 이 사용할 키의 인덱스. 모두 소진 시 len(api_keys)."""
        return self._current_index

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    @property
    def remaining_keys(self) -> int:
        return max(0, len(self._keys) - self._current_index)

    def reset(self) -> None:
        """다음 call() 부터 다시 첫 번째 키로 시도. (예: 일일 quota 리셋 시점)"""
        self._current_index = 0


# ---------------------------------------------------------------------------
# Predicate 헬퍼
# ---------------------------------------------------------------------------

def status_code_predicate(*exhausted_codes: int) -> Callable[[Any], bool]:
    """HTTP 응답의 status_code 가 지정된 코드면 quota 소진으로 판단.

    response.status_code 속성을 우선 본다 (httpx.Response, requests.Response).
    없으면 dict 의 'status_code' 키를 본다 (테스트 또는 어댑터된 응답).
    """
    codes = set(exhausted_codes)

    def _predicate(response: Any) -> bool:
        code = getattr(response, "status_code", None)
        if code is None and isinstance(response, dict):
            code = response.get("status_code")
        return code in codes

    return _predicate
