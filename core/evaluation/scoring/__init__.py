"""점수 산출 — 신호 list → 0~100 score 환산.

ScoreBuilder ABC 는 strategy 가 점수 계산 책임을 분리하기 위한 자리.
현재는 StubScoreBuilder 만 — 점수 산출 룰(가중치, 정규화 등) 은 도메인
의사결정 후 추가 구현.
"""
from core.evaluation.scoring.base import ScoreBuilder, ScoreInput, StubScoreBuilder

__all__ = ["ScoreBuilder", "ScoreInput", "StubScoreBuilder"]
