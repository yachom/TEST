"""Orchestrator — 결정적 흐름 제어.

자율 에이전트(Flow)와 결정적 컴포넌트(InitialCollector, OntologyMapper, ReportBuilder)를
정해진 순서로 호출. LLM 직접 호출 없음.

POC 골격: InitialCollector / OntologyMapper / ReportBuilder 는 Protocol 로 받는다.
실제 구현은 추후 라운드.

Observability:
    analyze() 시작 시 trace_scope() 컨텍스트를 연다.
    내부의 모든 TracingLLMClient 호출이 자동으로 같은 trace 에 속하게 됨.
    trace_backend 가 NoOpBackend 이면 외부 호출 0 — 기능 동일.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from core.agents.base import AgentContext, EvidenceTrace
from core.shared.infra.observability.base import TraceBackend, trace_scope
from core.shared.infra.observability.noop_backend import NoOpBackend

if TYPE_CHECKING:
    from core.agents.exploration.flow import ExplorationFlow
    from core.agents.qa.flow import QAFlow
    from core.shared.stores.graph_store import GraphStore
    from core.shared.stores.report_store import ReportStore


class InitialCollector(Protocol):
    def collect(self, address: str) -> list[dict]: ...


class OntologyMapper(Protocol):
    def map_all(self, raw_records: list[dict]) -> list: ...


class ReportBuilder(Protocol):
    def build(self, scope_id: str) -> dict: ...


@dataclass
class AnalysisResult:
    scope_id: str
    report: dict
    qa_flow: "QAFlow"
    evidence: EvidenceTrace


class Orchestrator:
    def __init__(
        self,
        initial_collector: InitialCollector,
        exploration_flow: "ExplorationFlow",
        ontology_mapper: OntologyMapper,
        graph_store: "GraphStore",
        report_builder: ReportBuilder,
        qa_flow: "QAFlow",
        report_store: "ReportStore | None" = None,
        trace_backend: TraceBackend | None = None,
    ) -> None:
        self._collector = initial_collector
        self._exploration = exploration_flow
        self._mapper = ontology_mapper
        self._graph = graph_store
        self._report_builder = report_builder
        self._qa = qa_flow
        self._report_store = report_store
        self._trace_backend = trace_backend or NoOpBackend()

    def analyze(self, address: str) -> AnalysisResult:
        scope_id = f"analysis_{uuid.uuid4().hex[:12]}"

        with trace_scope(
            self._trace_backend,
            name="address_analysis",
            trace_id=scope_id,
            metadata={"address": address},
        ):
            ctx = AgentContext(
                scope_id=scope_id,
                inputs={"address": address},
                artifacts={"initial_collection": self._collector.collect(address)},
            )

            ctx = self._exploration.run(ctx)

            all_raw = ctx.artifacts.get("initial_collection", []) + [
                r["result"] for r in ctx.artifacts.get("retrieved", [])
            ]
            graph_items = self._mapper.map_all(all_raw)
            for item in graph_items:
                self._write_graph_item(scope_id, item)

            report = self._report_builder.build(scope_id)
            if self._report_store is not None:
                self._report_store.save(address, report)

            return AnalysisResult(
                scope_id=scope_id,
                report=report,
                qa_flow=self._qa,
                evidence=ctx.evidence,
            )

    def _write_graph_item(self, scope_id: str, item) -> None:
        from core.shared.infra.graph_writer import GraphNode, GraphRelation

        if isinstance(item, GraphNode):
            self._graph.upsert_node(scope_id, item)
        elif isinstance(item, GraphRelation):
            self._graph.upsert_relation(scope_id, item)
