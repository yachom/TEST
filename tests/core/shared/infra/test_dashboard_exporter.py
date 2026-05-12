"""DashboardExporter NoOp placeholder smoke test."""
from __future__ import annotations

from pathlib import Path

from core.shared.infra.dashboard_exporter import (
    DashboardExporter,
    NoOpDashboardExporter,
)


def test_noop_dashboard_exporter_returns_zero_rows(tmp_path: Path):
    exp: DashboardExporter = NoOpDashboardExporter()
    out = exp.export("analysis_runs", tmp_path)
    assert out.dataset == "analysis_runs"
    assert out.output_path is None
    assert out.row_count == 0
