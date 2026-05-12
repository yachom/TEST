from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, TypedDict

from core.shared.config.settings import LLMSettings
from core.shared.infra.llm_client import LLMClient, LLMRequest, LLMResponse


class _GraphState(TypedDict, total=False):
    request: LLMRequest
    response: Any


@dataclass(frozen=True)
class LangChainModelConfig:
    provider: str
    model: str
    api_key: str
    temperature: float
    max_tokens: int
    timeout_seconds: float


class LangChainLLMClient(LLMClient):
    """LLMClient backed by LangChain chat models."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._model_config = LangChainModelConfig(
            provider=settings.provider,
            model=settings.model,
            api_key=settings.api_key,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout_seconds=settings.timeout_seconds,
        )
        self._chat_model = None
        self._graph = None

    def call(self, request: LLMRequest) -> LLMResponse:
        if self._graph is None:
            self._graph = self._build_graph()
        state = self._graph.invoke({"request": request})
        raw_response = state["response"]
        content = self._extract_content(raw_response)
        return LLMResponse(
            content=content,
            parsed=self._parse_content(content, request.response_schema),
            model=self.model_name(),
            usage=self._extract_usage(raw_response),
        )

    def model_name(self) -> str:
        return self._model_config.model

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as e:
            raise RuntimeError("LangGraph is not installed.") from e

        graph = StateGraph(_GraphState)
        graph.add_node("call_model", self._call_model_node)
        graph.add_edge(START, "call_model")
        graph.add_edge("call_model", END)
        return graph.compile()

    def _call_model_node(self, state: _GraphState) -> _GraphState:
        request = state["request"]
        model = self._get_chat_model()
        messages = [("system", request.system_prompt), ("human", request.user_prompt)]
        response = model.invoke(messages)
        return {"response": response}

    def _get_chat_model(self):
        if self._chat_model is not None:
            return self._chat_model
        provider = self._model_config.provider.lower()
        if provider in {"openai", "langchain_openai"}:
            if not self._model_config.api_key:
                raise RuntimeError(f"Missing API key. Set {self._settings.api_key_env}.")
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as e:
                raise RuntimeError("langchain-openai is not installed.") from e
            self._chat_model = ChatOpenAI(
                model=self._model_config.model,
                api_key=self._model_config.api_key,
                temperature=self._model_config.temperature,
                max_tokens=self._model_config.max_tokens,
                timeout=self._model_config.timeout_seconds,
            )
            return self._chat_model
        if provider in {"anthropic", "langchain_anthropic"}:
            if not self._model_config.api_key:
                raise RuntimeError(f"Missing API key. Set {self._settings.api_key_env}.")
            try:
                from langchain_anthropic import ChatAnthropic
            except ImportError as e:
                raise RuntimeError("langchain-anthropic is not installed. Run: pip install langchain-anthropic") from e
            self._chat_model = ChatAnthropic(
                model=self._model_config.model,
                api_key=self._model_config.api_key,
                temperature=self._model_config.temperature,
                max_tokens=self._model_config.max_tokens,
                timeout=self._model_config.timeout_seconds,
            )
            return self._chat_model
        raise ValueError(f"Unsupported LangChain LLM provider: {self._model_config.provider}")

    @staticmethod
    def _extract_content(raw_response: Any) -> str:
        content = getattr(raw_response, "content", raw_response)
        if isinstance(content, str):
            return content
        return json.dumps(content, ensure_ascii=False)

    @staticmethod
    def _parse_content(content: str, response_schema: dict | None) -> dict | None:
        if response_schema is None:
            return None
        text = content.strip()
        # Claude occasionally wraps JSON in markdown code fences — strip them
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _extract_usage(raw_response: Any) -> dict | None:
        usage = getattr(raw_response, "usage_metadata", None)
        if isinstance(usage, dict):
            return usage
        response_metadata = getattr(raw_response, "response_metadata", None)
        if isinstance(response_metadata, dict):
            token_usage = response_metadata.get("token_usage")
            return token_usage if isinstance(token_usage, dict) else None
        return None
