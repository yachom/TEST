"""IdentifierExtractor + NoOp/Registry-based placeholder smoke tests."""
from __future__ import annotations

from core.agents.identifier_extractor import (
    IdentifierAdapter,
    IdentifierExtractor,
    NoOpIdentifierExtractor,
    RegistryBasedIdentifierExtractor,
)


class _VworldAdapter(IdentifierAdapter):
    @property
    def source_type(self): return "vworld"
    def extract(self, raw):
        ids = raw.get("content", {}).get("identifiers", {})
        return {k: ids[k] for k in ("pnu", "lawd_cd") if k in ids}


def test_noop_extractor_returns_only_address():
    ext: IdentifierExtractor = NoOpIdentifierExtractor()
    pool = ext.extract("강남구 역삼동", [{"source_type": "vworld"}])
    assert pool == {"address": "강남구 역삼동"}


def test_registry_based_with_registered_adapter():
    ext = RegistryBasedIdentifierExtractor(registry={"vworld": _VworldAdapter()})
    raw = {
        "source_type": "vworld",
        "content": {"identifiers": {"pnu": "1168...", "lawd_cd": "11680"}},
    }
    pool = ext.extract("강남구", [raw])
    assert pool["address"] == "강남구"
    assert pool["pnu"] == "1168..."
    assert pool["lawd_cd"] == "11680"


def test_registry_based_ignores_unregistered_source():
    ext = RegistryBasedIdentifierExtractor(registry={"vworld": _VworldAdapter()})
    pool = ext.extract("주소", [{"source_type": "unknown", "content": {}}])
    assert pool == {"address": "주소"}


def test_registry_based_isolates_adapter_failure():
    class _BoomAdapter(IdentifierAdapter):
        @property
        def source_type(self): return "boom"
        def extract(self, raw):
            raise RuntimeError("kaboom")

    ext = RegistryBasedIdentifierExtractor(registry={"boom": _BoomAdapter()})
    pool = ext.extract("주소", [{"source_type": "boom"}])
    assert pool == {"address": "주소"}  # failure absorbed
