"""EvaluationClaimStore — 모든 차원의 EvaluationClaim 영구화 자리.

확장 자리. 대시보드 / 보고서 / 비교 분석의 핵심 raw 데이터.

설계 의도:
  - asset_id + target + dimension 단위로 query 가능
  - 시계열 (자산이 시간이 흐르며 어떻게 평가 변화하는지) 추적
  - 다중 자산 비교 (같은 dimension, 다른 asset_id)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.shared.domain.evaluation import EvaluationClaim, EvaluationDimension


class EvaluationClaimStore(ABC):
    """EvaluationClaim 영구화."""

    @abstractmethod
    def save(self, claim: "EvaluationClaim") -> str:
        """Claim 저장 후 claim_id 반환."""

    @abstractmethod
    def save_many(self, claims: list["EvaluationClaim"]) -> list[str]: ...

    @abstractmethod
    def find_by_asset(
        self,
        asset_id: str,
        dimension: "EvaluationDimension | None" = None,
    ) -> list["EvaluationClaim"]: ...

    @abstractmethod
    def find_by_scope(self, scope_id: str) -> list["EvaluationClaim"]: ...


class InMemoryEvaluationClaimStore(EvaluationClaimStore):
    """POC 휘발 구현."""

    def __init__(self) -> None:
        self._claims: list = []  # list[(claim_id, scope_id, EvaluationClaim)]
        self._counter = 0

    def save(self, claim) -> str:
        self._counter += 1
        claim_id = f"claim_{self._counter}"
        scope_id = getattr(claim, "scope_id", "") or claim.metadata.get("scope_id", "")
        self._claims.append((claim_id, scope_id, claim))
        return claim_id

    def save_many(self, claims) -> list[str]:
        return [self.save(c) for c in claims]

    def find_by_asset(self, asset_id, dimension=None):
        out = []
        for _cid, _sid, c in self._claims:
            if c.asset_id != asset_id:
                continue
            if dimension is not None and c.dimension != dimension:
                continue
            out.append(c)
        return out

    def find_by_scope(self, scope_id):
        return [c for _cid, sid, c in self._claims if sid == scope_id]
