"""LLM Agent Tool 베이스 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """LLM Agent가 호출하는 Tool의 공통 인터페이스.

    Tool은 비즈니스 로직을 직접 갖지 않는다.
    Application Service를 호출하는 얇은 어댑터 역할만 한다.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool 식별자."""

    @property
    @abstractmethod
    def description(self) -> str:
        """LLM이 이 Tool을 선택하는 데 사용하는 설명."""

    @abstractmethod
    def run(self, **kwargs) -> dict:
        """Tool 실행. 항상 dict를 반환한다 (LangChain / MCP 호환)."""
