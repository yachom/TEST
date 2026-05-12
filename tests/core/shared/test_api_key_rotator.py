"""ApiKeyRotator 단위 테스트."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.shared.infra.api_key_rotator import (
    AllKeysExhaustedError,
    ApiKeyRotator,
    status_code_predicate,
)


@dataclass
class _FakeResponse:
    status_code: int
    body: str = ""


def test_returns_first_key_response_when_not_exhausted():
    rotator = ApiKeyRotator(
        api_keys=["k1", "k2"],
        is_exhausted=status_code_predicate(403),
    )
    response = rotator.call(lambda key: _FakeResponse(status_code=200, body=key))

    assert response.status_code == 200
    assert response.body == "k1"
    assert rotator.current_key_index == 0


def test_falls_through_to_next_key_when_first_exhausted():
    calls: list[str] = []

    def fn(key: str) -> _FakeResponse:
        calls.append(key)
        return _FakeResponse(status_code=403) if key == "k1" else _FakeResponse(status_code=200, body=key)

    rotator = ApiKeyRotator(api_keys=["k1", "k2"], is_exhausted=status_code_predicate(403))
    response = rotator.call(fn)

    assert calls == ["k1", "k2"]
    assert response.body == "k2"
    assert rotator.current_key_index == 1


def test_skips_exhausted_keys_on_subsequent_calls():
    calls: list[str] = []

    def fn(key: str) -> _FakeResponse:
        calls.append(key)
        return _FakeResponse(status_code=403) if key == "k1" else _FakeResponse(status_code=200, body=key)

    rotator = ApiKeyRotator(api_keys=["k1", "k2"], is_exhausted=status_code_predicate(403))
    rotator.call(fn)
    rotator.call(fn)

    assert calls == ["k1", "k2", "k2"]


def test_raises_when_all_keys_exhausted():
    rotator = ApiKeyRotator(
        api_keys=["k1", "k2"],
        is_exhausted=status_code_predicate(403, 429),
    )

    with pytest.raises(AllKeysExhaustedError) as exc_info:
        rotator.call(lambda key: _FakeResponse(status_code=429))

    assert exc_info.value.key_count == 2
    assert exc_info.value.last_response.status_code == 429
    assert rotator.remaining_keys == 0


def test_reset_returns_to_first_key():
    rotator = ApiKeyRotator(api_keys=["k1", "k2"], is_exhausted=status_code_predicate(403))

    with pytest.raises(AllKeysExhaustedError):
        rotator.call(lambda key: _FakeResponse(status_code=403))
    assert rotator.current_key_index == 2

    rotator.reset()
    assert rotator.current_key_index == 0
    response = rotator.call(lambda key: _FakeResponse(status_code=200, body=key))
    assert response.body == "k1"


def test_supports_compound_key_types():
    """API 키가 (client_id, client_secret) 튜플 같은 복합 형태도 지원."""
    rotator = ApiKeyRotator(
        api_keys=[("cid1", "secret1"), ("cid2", "secret2")],
        is_exhausted=status_code_predicate(403),
    )

    def fn(creds: tuple[str, str]) -> _FakeResponse:
        cid, _ = creds
        return _FakeResponse(status_code=403) if cid == "cid1" else _FakeResponse(status_code=200, body=cid)

    response = rotator.call(fn)
    assert response.body == "cid2"


def test_predicate_can_inspect_response_body():
    """구글식: 200 응답이지만 body 의 errorCode 로 quota 소진 판단."""
    def is_exhausted(resp: dict) -> bool:
        return resp.get("error", {}).get("code") == 429

    rotator = ApiKeyRotator(api_keys=["k1", "k2"], is_exhausted=is_exhausted)

    def fn(key: str) -> dict:
        if key == "k1":
            return {"error": {"code": 429, "message": "quota exceeded"}}
        return {"data": ["item"], "used_key": key}

    response = rotator.call(fn)
    assert response == {"data": ["item"], "used_key": "k2"}


def test_status_code_predicate_works_with_dict():
    pred = status_code_predicate(403)
    assert pred({"status_code": 403}) is True
    assert pred({"status_code": 200}) is False
    assert pred({}) is False


def test_empty_api_keys_rejected():
    with pytest.raises(ValueError):
        ApiKeyRotator(api_keys=[], is_exhausted=status_code_predicate(403))
