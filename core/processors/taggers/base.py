"""OntologyTagger 추상 인터페이스 — 스키마 주입식."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.collectors.news.models import NewsArticle
    from core.processors.taggers.models import OntologyTag
    from core.shared.infra.llm_client import LLMClient


class OntologyTagger(ABC):
    """자산별 평가 요인 사전을 주입받아 동작하는 온톨로지 태거.

    스키마(평가 요인 사전)은 자산별로 다르지만, 태깅 흐름은 동일하다.
    """

    def __init__(self, llm_client: "LLMClient", evaluation_factors: list[str]) -> None:
        self._llm = llm_client
        self._evaluation_factors = evaluation_factors

    @abstractmethod
    def tag(self, article: "NewsArticle") -> "OntologyTag":
        ...
