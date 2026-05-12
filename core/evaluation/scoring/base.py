"""ScoreBuilder — 신호 모음을 0~100 점수로 환산하는 자리.

확장 자리. 현재 구현체 (`StubScoreBuilder`) 는 항상 0.0 반환.

향후 후보 구현:
  WeightedSignalScoreBuilder — influence_strength × influence_direction × confidence
                                의 가중합 → tanh 정규화 → 0~100
  LLMRubricScoreBuilder      — LLM 에 신호 list + rubric 주고 점수 추출
  HybridScoreBuilder         — 위 둘의 ensemble

분리 이유:
  - Strategy 와 점수 산출 규칙을 분리 → 같은 strategy 로 여러 scoring 가능
  - A/B 테스트 자리 (다른 ScoreBuilder 로 같은 신호 재평가)
  - 도메인 의사결정자가 ScoreBuilder 만 수정하면 됨 (Strategy 코드 안 봐도)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScoreInput:
    """점수 산출에 필요한 입력 묶음.

    target_key 는 신호 필터링 / target 별 점수 분기를 위해.
    metadata 에 자산별 추가 컨텍스트 (예: 입지 가중치) 주입 가능.
    """
    asset_id: str
    target_key: str
    dimension: str
    signals: list[dict]
    metadata: dict = field(default_factory=dict)


@dataclass
class ScoreOutput:
    """점수 + 산출 근거 요약."""
    score: float                  # 0.0 ~ 100.0
    rationale: str
    contributions: list[dict] = field(default_factory=list)  # signal 별 기여도


class ScoreBuilder(ABC):
    """신호 list → 점수 환산기."""

    @abstractmethod
    def build(self, inp: ScoreInput) -> ScoreOutput: ...


class StubScoreBuilder(ScoreBuilder):
    """POC placeholder — 점수 산출 룰 결정 전까지 0.0 반환.

    rationale 에 신호 개수만 표기 → claim 자체는 생성되어 흐름 검증 가능.
    """

    def build(self, inp: ScoreInput) -> ScoreOutput:
        n = len(inp.signals)
        if n == 0:
            return ScoreOutput(score=0.0, rationale="적용 가능한 신호 없음 (stub).")
        return ScoreOutput(
            score=0.0,
            rationale=f"{n}개 신호 식별 — 점수 산출 룰 미구현 (stub).",
            contributions=[],
        )
