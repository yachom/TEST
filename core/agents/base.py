"""에이전트 공통 추상화 — Agent ABC, 실행 컨텍스트, evidence trace.

Flow 안의 서브에이전트(Planner, Retriever, Critic, Analyzer 등)도
이 Agent ABC 를 구현한다. Flow 자체도 외부에서 보면 하나의 Agent.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EvidenceStep:
    """에이전트가 수행한 한 단계의 흔적.

    rationale 은 LLM 이 이 단계를 선택한 이유.
    result_summary 는 도구/서브에이전트 응답의 축약 (원본은 artifacts 에).
    """
    step_id: int
    actor: str                                  # (서브)에이전트 식별자
    tool_name: str
    rationale: str
    input_summary: dict
    result_summary: dict
    occurred_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EvidenceTrace:
    """Flow 단위 evidence 누적 — 보고서/QA 의 근거 체인."""
    scope_id: str
    steps: list[EvidenceStep] = field(default_factory=list)

    def append(self, step: EvidenceStep) -> None:
        self.steps.append(step)

    def next_step_id(self) -> int:
        return len(self.steps) + 1

    def __len__(self) -> int:
        return len(self.steps)


@dataclass
class AgentContext:
    """에이전트 실행 컨텍스트.

    Flow 안의 서브에이전트들이 같은 AgentContext 를 주고받으며 상태 누적.
    artifacts 는 단계 간 공유 산출물 (수집된 raw data, 중간 매핑 결과 등).
    """
    scope_id: str
    inputs: dict
    artifacts: dict = field(default_factory=dict)
    evidence: EvidenceTrace = field(default_factory=lambda: EvidenceTrace(scope_id=""))

    def __post_init__(self) -> None:
        if not self.evidence.scope_id:
            self.evidence.scope_id = self.scope_id


class Agent(ABC):
    """모든 (서브)에이전트의 공통 인터페이스."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def run(self, context: AgentContext) -> AgentContext:
        ...
