"""DashboardExporter — 영구 저장된 raw 데이터를 외부 BI 도구가 읽을 수 있는 형태로 export.

확장 자리. 후보 구현:
  CsvDashboardExporter      — CSV 파일로 dump
  JsonDashboardExporter     — JSON Lines
  ParquetDashboardExporter  — pyarrow 기반, BigQuery / Athena 호환
  PostgresViewExporter      — SQL VIEW 만 생성, BI 도구가 직접 join

POC 단계: NoOpDashboardExporter 만. 영구 저장 (AnalysisRunStore / EvaluationClaimStore /
LLMCallRecorder) 가 실제 구현되기 전까지는 출력할 데이터가 없으므로 active 구현 보류.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.shared.stores.analysis_run_store import AnalysisRunStore
    from core.shared.stores.evaluation_claim_store import EvaluationClaimStore
    from core.shared.infra.observability.recorders import LLMCallRecorder


DatasetName = Literal["analysis_runs", "evaluation_claims", "llm_calls"]


@dataclass
class ExportResult:
    dataset: str
    output_path: str | None
    row_count: int


class DashboardExporter(ABC):
    """raw 데이터 → 대시보드 도구 호환 포맷."""

    @abstractmethod
    def export(
        self,
        dataset: DatasetName,
        output_dir: Path,
        *,
        since: str | None = None,
    ) -> ExportResult: ...


class NoOpDashboardExporter(DashboardExporter):
    """POC placeholder — 실제 저장소가 SQLite 로 채워지면 CsvDashboardExporter 등으로 교체."""

    def export(
        self,
        dataset: DatasetName,
        output_dir: Path,
        *,
        since: str | None = None,
    ) -> ExportResult:
        return ExportResult(dataset=dataset, output_path=None, row_count=0)
