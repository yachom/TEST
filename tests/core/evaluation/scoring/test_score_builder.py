"""ScoreBuilder ABC + StubScoreBuilder placeholder smoke tests."""
from __future__ import annotations

from core.evaluation.scoring import ScoreBuilder, ScoreInput, StubScoreBuilder


def test_stub_score_builder_returns_zero_with_signals():
    builder: ScoreBuilder = StubScoreBuilder()
    out = builder.build(ScoreInput(
        asset_id="a1",
        target_key="building:PNU",
        dimension="sentiment",
        signals=[{"summary": "s1"}, {"summary": "s2"}],
    ))
    assert out.score == 0.0
    assert "2개 신호 식별" in out.rationale


def test_stub_score_builder_empty_signals():
    out = StubScoreBuilder().build(ScoreInput(
        asset_id="a1", target_key="t1", dimension="sentiment", signals=[]
    ))
    assert out.score == 0.0
    assert "신호 없음" in out.rationale
