"""SecretProvider 추상화 + EnvSecretProvider / ChainSecretProvider / Static smoke tests."""
from __future__ import annotations

import os

from core.shared.config.secrets import (
    ChainSecretProvider,
    EnvSecretProvider,
    SecretProvider,
    StaticSecretProvider,
)


def test_env_secret_provider_reads_from_os_environ(monkeypatch):
    monkeypatch.setenv("FNPRICING_TEST_KEY", "abc123")
    p: SecretProvider = EnvSecretProvider()
    assert p.get("FNPRICING_TEST_KEY") == "abc123"


def test_env_secret_provider_returns_default_for_missing(monkeypatch):
    monkeypatch.delenv("FNPRICING_NONEXISTENT", raising=False)
    p = EnvSecretProvider()
    assert p.get("FNPRICING_NONEXISTENT") == ""
    assert p.get("FNPRICING_NONEXISTENT", default="fallback") == "fallback"


def test_static_provider():
    p = StaticSecretProvider({"K": "v"})
    assert p.get("K") == "v"
    assert p.get("missing") == ""


def test_chain_provider_returns_first_nonempty(monkeypatch):
    monkeypatch.delenv("CHAIN_TEST_KEY", raising=False)
    chain = ChainSecretProvider([
        StaticSecretProvider({"OTHER": "x"}),       # 미스
        EnvSecretProvider(),                         # 빈 환경
        StaticSecretProvider({"CHAIN_TEST_KEY": "from_chain"}),
    ])
    assert chain.get("CHAIN_TEST_KEY") == "from_chain"


def test_chain_provider_empty_list_raises():
    import pytest
    with pytest.raises(ValueError):
        ChainSecretProvider([])
