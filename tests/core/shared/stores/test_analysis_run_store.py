"""AnalysisRunStore + InMemory placeholder smoke tests."""
from __future__ import annotations

from datetime import datetime, timedelta

from core.shared.stores.analysis_run_store import (
    AnalysisRunRecord,
    AnalysisRunStore,
    InMemoryAnalysisRunStore,
)


def _make_record(scope_id, started=None) -> AnalysisRunRecord:
    return AnalysisRunRecord(
        scope_id=scope_id,
        asset_class="commercial",
        address="강남구",
        started_at=started or datetime.utcnow(),
    )


def test_save_and_get():
    store: AnalysisRunStore = InMemoryAnalysisRunStore()
    rec = _make_record("analysis_1")
    store.save(rec)
    fetched = store.get("analysis_1")
    assert fetched is not None
    assert fetched.scope_id == "analysis_1"


def test_get_missing_returns_none():
    assert InMemoryAnalysisRunStore().get("nope") is None


def test_list_recent_orders_by_started_desc():
    store = InMemoryAnalysisRunStore()
    base = datetime.utcnow()
    store.save(_make_record("a", base - timedelta(hours=2)))
    store.save(_make_record("b", base - timedelta(hours=1)))
    store.save(_make_record("c", base))
    recent = store.list_recent(limit=10)
    assert [r.scope_id for r in recent] == ["c", "b", "a"]


def test_elapsed_seconds_property():
    rec = _make_record("x")
    rec.finished_at = rec.started_at + timedelta(seconds=12)
    assert abs(rec.elapsed_seconds - 12.0) < 1e-6
