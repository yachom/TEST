from __future__ import annotations

import math
from typing import Optional

from core.collectors.news.repositories.embedding_repository import EmbeddingRepository


class InMemoryEmbeddingRepository(EmbeddingRepository):
    """테스트용 인메모리 임베딩 저장소 — 코사인 유사도 검색."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[list[float], str]] = {}

    def save(self, article_id: str, vector: list[float], model: str) -> None:
        self._store[article_id] = (vector, model)

    def get_vector(self, article_id: str) -> Optional[list[float]]:
        entry = self._store.get(article_id)
        return entry[0] if entry else None

    def find_similar(
        self,
        vector: list[float],
        threshold: float,
        exclude_id: str | None = None,
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        results = []
        for aid, (v, _) in self._store.items():
            if aid == exclude_id:
                continue
            sim = self._cosine(vector, v)
            if sim >= threshold:
                results.append((aid, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x ** 2 for x in a))
        mag_b = math.sqrt(sum(x ** 2 for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
