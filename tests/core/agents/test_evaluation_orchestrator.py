"""EvaluationOrchestrator + placeholder 구현체 smoke tests."""
from __future__ import annotations

from datetime import datetime

from core.agents.evaluation_orchestrator import (
    DefaultEvaluationOrchestrator,
    NoOpEvaluationOrchestrator,
)
from core.evaluation.base import EvaluationStrategy
from core.shared.domain.asset import AssetClass
from core.shared.domain.evaluation import (
    AssetProfile,
    EvaluationClaim,
    EvaluationDimension,
    EvaluationTarget,
)


class _DummyTarget(EvaluationTarget):
    target_type = "dummy"
    def unique_key(self): return "dummy:1"
    def label(self): return "Dummy"


class _ConstantStrategy(EvaluationStrategy):
    def __init__(self, dim, score):
        self._dim = dim
        self._score = score
    @property
    def dimension(self):
        return self._dim
    def evaluate(self, asset_id, profile):
        return [EvaluationClaim(
            asset_id=asset_id, target=_DummyTarget(),
            dimension=self._dim, score=self._score,
            evidence=[], rationale="test", created_at=datetime.utcnow(),
        )]


class _BoomStrategy(EvaluationStrategy):
    @property
    def dimension(self):
        return EvaluationDimension.STRUCTURAL
    def evaluate(self, asset_id, profile):
        raise RuntimeError("boom")


def _profile_with_dims(dims):
    return AssetProfile(
        asset_class=AssetClass.COMMERCIAL,
        evaluation_dimensions=dims,
        sentiment_target_types=[],
        collector_source_types=[],
        config_path=__import__("pathlib").Path("/tmp/nonexistent"),
        ontology_schema_module="x",
    )


def test_noop_orchestrator_returns_empty_list():
    profile = _profile_with_dims([EvaluationDimension.SENTIMENT])
    claims = NoOpEvaluationOrchestrator().evaluate("asset_x", profile)
    assert claims == []


def test_default_orchestrator_collects_claims_per_dimension():
    strategies = {
        EvaluationDimension.SENTIMENT: _ConstantStrategy(EvaluationDimension.SENTIMENT, 50.0),
        EvaluationDimension.QUANTITATIVE: _ConstantStrategy(EvaluationDimension.QUANTITATIVE, 70.0),
    }
    orch = DefaultEvaluationOrchestrator(strategies=strategies)
    profile = _profile_with_dims([
        EvaluationDimension.SENTIMENT,
        EvaluationDimension.QUANTITATIVE,
    ])
    claims = orch.evaluate("asset_x", profile)
    assert len(claims) == 2
    dims = {c.dimension for c in claims}
    assert dims == {EvaluationDimension.SENTIMENT, EvaluationDimension.QUANTITATIVE}


def test_default_orchestrator_isolates_strategy_failure():
    """한 전략 실패가 전체를 막지 않게 격리."""
    strategies = {
        EvaluationDimension.SENTIMENT: _ConstantStrategy(EvaluationDimension.SENTIMENT, 50.0),
        EvaluationDimension.STRUCTURAL: _BoomStrategy(),
    }
    orch = DefaultEvaluationOrchestrator(strategies=strategies)
    profile = _profile_with_dims([
        EvaluationDimension.SENTIMENT,
        EvaluationDimension.STRUCTURAL,
    ])
    claims = orch.evaluate("asset_x", profile)
    # Sentiment 만 성공 → 1 개 claim
    assert len(claims) == 1
    assert claims[0].dimension == EvaluationDimension.SENTIMENT


def test_default_orchestrator_skips_dim_without_strategy():
    orch = DefaultEvaluationOrchestrator(strategies={})
    profile = _profile_with_dims([EvaluationDimension.SENTIMENT])
    assert orch.evaluate("a", profile) == []
