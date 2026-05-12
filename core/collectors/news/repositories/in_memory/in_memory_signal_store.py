from __future__ import annotations

import uuid
from typing import Optional

from core.shared.stores.signal_store import SignalStore


class InMemorySignalStore(SignalStore):
    """테스트용 인메모리 Signal 저장소."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def upsert(self, signal: dict) -> str:
        article_id = signal.get("article_id", str(uuid.uuid4()))
        signal_id = f"sig:{article_id}"
        self._store[signal_id] = {**signal, "signal_id": signal_id}
        return signal_id

    def get(self, signal_id: str) -> Optional[dict]:
        return self._store.get(signal_id)

    def query_by_asset(self, asset_class: str, limit: int = 50) -> list[dict]:
        return [s for s in self._store.values() if s.get("asset_class") == asset_class][:limit]

    def query_by_region(self, region_code: str, limit: int = 50) -> list[dict]:
        return [s for s in self._store.values() if s.get("region_code") == region_code][:limit]

    def query_by_signal_type(self, signal_type: str, limit: int = 50) -> list[dict]:
        return [s for s in self._store.values() if s.get("signal_type") == signal_type][:limit]

    def query_applicable(self, asset_class: str, region_code: Optional[str] = None) -> list[dict]:
        results = [
            s for s in self._store.values()
            if s.get("asset_class") == asset_class
            and s.get("applicability") in ("direct", "needs_verification")
        ]
        if region_code:
            results = [s for s in results if s.get("region_code") == region_code]
        return results
