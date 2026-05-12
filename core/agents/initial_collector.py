"""InitialCollector — 결정적 1차 공적 정보 수집기.

주소를 받아 등록된 도구들을 정해진 순서로 호출. 자율성 없음.
실제 도구는 추후 vworld / 건축허브 / 상가 API 등으로 교체.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.tools.base import BaseTool


class InitialCollector:
    def __init__(self, tools: list["BaseTool"]) -> None:
        self._tools = tools

    def collect(self, address: str) -> list[dict]:
        return [tool.run(address=address) for tool in self._tools]
