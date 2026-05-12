from __future__ import annotations

from typing import Optional

from core.collectors.news.repositories.ontology_tag_repository import OntologyTagRepository
from core.processors.taggers.models import OntologyTag


class InMemoryOntologyTagRepository(OntologyTagRepository):
    """테스트용 인메모리 온톨로지 태그 저장소."""

    def __init__(self) -> None:
        self._store: dict[str, OntologyTag] = {}
        self._graph_done: set[str] = set()

    def save(self, tag: OntologyTag) -> None:
        self._store[tag.article_id] = tag

    def get(self, article_id: str) -> Optional[OntologyTag]:
        return self._store.get(article_id)

    def find_pending_graph(self) -> list[OntologyTag]:
        return [t for aid, t in self._store.items() if aid not in self._graph_done]

    def find_by_asset_class(self, asset_class: str, limit: int = 100) -> list[OntologyTag]:
        return [t for t in self._store.values() if t.asset_class == asset_class][:limit]

    def mark_graph_done(self, article_id: str) -> None:
        self._graph_done.add(article_id)

    def all(self) -> list[OntologyTag]:
        return list(self._store.values())
