"""IdentifierExtractor — 1차 수집물 → 식별자/속성 pool 추출.

확장 자리. 주소 외 입력 차원 (PNU, lawd_cd, 사업자번호, 좌표, ...) 으로
새 도구 호출의 길을 여는 핵심.

설계 의도:
  InitialCollector 가 주소를 받아 1차 raw 수집 → IdentifierExtractor 가
  raw 들을 보고 가용 식별자 dict 를 추출 → ExplorationFlow.Planner 가 그
  식별자들을 prompt 에 노출 → 다른 입력 차원의 도구들을 자율 호출.

  ctx.artifacts["identifier_pool"] = {
      "address": ..., "pnu": ..., "lawd_cd": ..., "bjdong_cd": ...,
      "approval_date": ..., "main_purpose": ..., ...
  }

POC 시점: NoOpIdentifierExtractor — pool 은 input address 하나만.
추후 RegistryBasedIdentifierExtractor 가 source_type 별 어댑터로 자동 추출.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IdentifierExtractor(ABC):
    """1차 수집 raw_records → identifier pool dict 추출."""

    @abstractmethod
    def extract(self, address: str, raw_records: list[dict]) -> dict[str, str]: ...


class NoOpIdentifierExtractor(IdentifierExtractor):
    """기본 — 입력 주소만 pool 에 포함. 추출 로직 미구현."""

    def extract(self, address: str, raw_records: list[dict]) -> dict[str, str]:
        return {"address": address}


class IdentifierAdapter(ABC):
    """source_type 별 식별자 추출 어댑터.

    OntologyMapper.BaseAdapter 와 평행 구조. raw["source_type"] 으로 라우팅.
    """

    @property
    @abstractmethod
    def source_type(self) -> str: ...

    @abstractmethod
    def extract(self, raw: dict) -> dict[str, str]: ...


class RegistryBasedIdentifierExtractor(IdentifierExtractor):
    """어댑터 registry 기반 추출 — 추후 확장 시 본격 사용.

    현재는 빈 registry 면 NoOp 와 동일. 어댑터를 등록할 때마다 pool 이 풍부해진다.
    """

    def __init__(self, registry: dict[str, IdentifierAdapter] | None = None) -> None:
        self._registry = registry or {}

    def extract(self, address: str, raw_records: list[dict]) -> dict[str, str]:
        pool: dict[str, str] = {"address": address}
        for raw in raw_records:
            source_type = raw.get("source_type", "")
            adapter = self._registry.get(source_type)
            if adapter is None:
                continue
            try:
                extracted = adapter.extract(raw)
            except Exception:
                continue
            for key, value in extracted.items():
                # 이미 더 일찍 추출된 값은 보존 (먼저 들어온 것 우선)
                if key not in pool and value:
                    pool[key] = str(value)
        return pool
