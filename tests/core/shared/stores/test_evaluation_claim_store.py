"""EvaluationClaimStore + InMemory placeholder smoke tests."""
from __future__ import annotations

from datetime import datetime

from core.shared.domain.evaluation import (
    EvaluationClaim,
    EvaluationDimension,
    EvaluationTarget,
)
from core.shared.stores.evaluation_claim_store import (
    EvaluationClaimStore,
    InMemoryEvaluationClaimStore,
)


class _T(EvaluationTarget):
    target_type = "t"
    def unique_key(self): return "t:1"
    def label(self): return "T"


def _claim(asset_id, dim) -> EvaluationClaim:
    return EvaluationClaim(
        asset_id=asset_id, target=_T(),
        dimension=dim, score=0.0,
        evidence=[], rationale="", created_at=datetime.utcnow(),
    )


def test_save_and_find_by_asset():
    store: EvaluationClaimStore = InMemoryEvaluationClaimStore()
    store.save(_claim("a1", EvaluationDimension.SENTIMENT))
    store.save(_claim("a1", EvaluationDimension.QUANTITATIVE))
    store.save(_claim("a2", EvaluationDimension.SENTIMENT))

    a1_claims = store.find_by_asset("a1")
    assert len(a1_claims) == 2

    a1_sentiment = store.find_by_asset("a1", EvaluationDimension.SENTIMENT)
    assert len(a1_sentiment) == 1
    assert a1_sentiment[0].dimension == EvaluationDimension.SENTIMENT


def test_save_many():
    store = InMemoryEvaluationClaimStore()
    ids = store.save_many([
        _claim("a", EvaluationDimension.SENTIMENT),
        _claim("b", EvaluationDimension.STRUCTURAL),
    ])
    assert len(ids) == 2
    assert ids[0] != ids[1]
