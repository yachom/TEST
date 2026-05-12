from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMRequest:
    system_prompt: str
    user_prompt: str
    response_schema: dict | None = None
    temperature: float = 0.0
    max_tokens: int = 2048


@dataclass
class LLMResponse:
    content: str
    parsed: dict | None = None
    model: str = ""
    usage: dict | None = None


class LLMClient(ABC):
    @abstractmethod
    def call(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    def model_name(self) -> str:
        ...


class StubLLMClient(LLMClient):
    """테스트 및 초기 구현용 Stub."""

    def call(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(content="{}", parsed={}, model="stub", usage={"input_tokens": 0, "output_tokens": 0})

    def model_name(self) -> str:
        return "stub"
