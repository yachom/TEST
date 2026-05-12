from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RunSummary:
    run_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    search: dict = field(default_factory=dict)
    filter: dict = field(default_factory=dict)
    embedding: dict = field(default_factory=dict)
    dedup: dict = field(default_factory=dict)
    tagging: dict = field(default_factory=dict)
    graph: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def elapsed_seconds(self) -> Optional[float]:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class RunSummaryService:
    """DAG 실행 전체의 요약을 수집하고 기록한다."""

    def __init__(self) -> None:
        self._summary: Optional[RunSummary] = None

    def start(self, run_id: str) -> RunSummary:
        self._summary = RunSummary(run_id=run_id, started_at=datetime.utcnow())
        return self._summary

    def record_search(self, result) -> None:
        if self._summary is None:
            return
        self._summary.search = {
            "total_fetched": result.total_fetched,
            "new_saved": result.new_saved,
            "url_duplicates": result.url_duplicates,
            "hash_duplicates": result.hash_duplicates,
        }

    def record_filter(self, results: list) -> None:
        if self._summary is None:
            return
        passed = sum(1 for r in results if r.passed)
        self._summary.filter = {"total": len(results), "passed": passed, "excluded": len(results) - passed}

    def record_embedding(self, results: list) -> None:
        if self._summary is None:
            return
        ok = sum(1 for r in results if r.success)
        self._summary.embedding = {"total": len(results), "success": ok, "failed": len(results) - ok}

    def record_dedup(self, results: list) -> None:
        if self._summary is None:
            return
        novel = sum(1 for r in results if r.is_novel)
        self._summary.dedup = {"total": len(results), "novel": novel, "duplicate": len(results) - novel}

    def record_tagging(self, results: list) -> None:
        if self._summary is None:
            return
        ok = sum(1 for r in results if r.success)
        self._summary.tagging = {"total": len(results), "success": ok, "failed": len(results) - ok}

    def record_graph(self, candidates: list) -> None:
        if self._summary is None:
            return
        eligible = sum(1 for c in candidates if c.is_graph_eligible)
        self._summary.graph = {"total": len(candidates), "queued": eligible, "excluded": len(candidates) - eligible}

    def finish(self) -> Optional[RunSummary]:
        if self._summary is None:
            return None
        self._summary.finished_at = datetime.utcnow()
        return self._summary
