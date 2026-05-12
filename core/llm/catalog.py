"""PromptCatalog — 키 기반 prompt 템플릿 로드/렌더링.

각 에이전트/서비스가 직접 prompt 문자열을 들지 않고:
    rendered = catalog.render("exploration.planner", tools="...", address="...")
    response = llm.call(rendered.to_llm_request())

YAML 1 파일 = 1 prompt:
    version: 1
    description: "한 줄 설명"
    system: |
      ...
    user: |
      ...
    schema: { ... JSON schema ... }

키는 디렉토리 경로의 도트 표기: "exploration.planner" → prompts/exploration/planner.yaml.

렌더링:
  string.Template ($var 표기) 사용. prompt 안의 JSON 예시 {"key": ...} 와 충돌하지 않게.
  $var / ${var} 가 변수, $$ 가 literal $. Jinja2 미도입 — 단순/가벼움 우선.

version_hash:
  system + user + schema 의 sha256 prefix.
  Langfuse 등 observability 메타로 송신하여 회귀 추적.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Mapping

import yaml


_DEFAULT_ROOT = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    """원본 템플릿 (렌더링 전)."""
    key: str
    version: int
    description: str
    system_template: str
    user_template: str
    response_schema: dict | None
    version_hash: str
    source_path: Path


@dataclass(frozen=True)
class RenderedPrompt:
    """변수 치환이 끝난 prompt — LLMRequest 로 변환 가능."""
    key: str
    version: int
    version_hash: str
    system: str
    user: str
    response_schema: dict | None

    def to_llm_request(
        self,
        *,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ):
        """LLMRequest 객체로 변환.

        지연 import — 이 모듈은 core.shared.infra.llm_client 에만 의존.
        """
        from core.shared.infra.llm_client import LLMRequest
        return LLMRequest(
            system_prompt=self.system,
            user_prompt=self.user,
            response_schema=self.response_schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class PromptCatalog:
    """Prompt 템플릿 디렉토리를 로드/캐시/렌더링.

    기본 root: core/llm/prompts/. 테스트 격리 시 root 인자로 override.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path(root) if root else _DEFAULT_ROOT
        self._cache: dict[str, PromptTemplate] = {}

    @property
    def root(self) -> Path:
        return self._root

    def get(self, key: str) -> PromptTemplate:
        if key in self._cache:
            return self._cache[key]
        path = self._resolve_path(key)
        template = self._load_yaml(key, path)
        self._cache[key] = template
        return template

    def render(self, key: str, **variables: Any) -> RenderedPrompt:
        template = self.get(key)
        system = _safe_format(template.system_template, variables)
        user = _safe_format(template.user_template, variables)
        return RenderedPrompt(
            key=template.key,
            version=template.version,
            version_hash=template.version_hash,
            system=system,
            user=user,
            response_schema=template.response_schema,
        )

    def list_keys(self) -> list[str]:
        """root 디렉토리를 walk 해서 등록된 모든 prompt 키 반환."""
        keys: list[str] = []
        for path in sorted(self._root.rglob("*.yaml")):
            rel = path.relative_to(self._root).with_suffix("")
            keys.append(".".join(rel.parts))
        return keys

    def _resolve_path(self, key: str) -> Path:
        parts = key.split(".")
        path = self._root.joinpath(*parts).with_suffix(".yaml")
        if not path.exists():
            raise PromptNotFoundError(
                f"Prompt key '{key}' not found at expected path: {path}"
            )
        return path

    @staticmethod
    def _load_yaml(key: str, path: Path) -> PromptTemplate:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        system_template = str(raw.get("system", "")).strip()
        user_template = str(raw.get("user", "")).strip()
        schema = raw.get("schema")
        if schema is not None and not isinstance(schema, dict):
            raise PromptDefinitionError(f"{path}: 'schema' must be a dict if present")

        version_hash = _hash_template(system_template, user_template, schema)
        return PromptTemplate(
            key=key,
            version=int(raw.get("version", 1)),
            description=str(raw.get("description", "")),
            system_template=system_template,
            user_template=user_template,
            response_schema=schema,
            version_hash=version_hash,
            source_path=path,
        )


class PromptNotFoundError(KeyError):
    """요청한 key 에 해당하는 prompt 파일이 없음."""


class PromptDefinitionError(ValueError):
    """prompt YAML 자체가 형식에 안 맞음."""


def _hash_template(system: str, user: str, schema: dict | None) -> str:
    """system + user + schema 직렬화의 sha256 앞 12자."""
    payload = json.dumps(
        {"system": system, "user": user, "schema": schema},
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _safe_format(template: str, variables: Mapping[str, Any]) -> str:
    """string.Template.substitute 호출.

    $var 또는 ${var} 가 변수 위치. $$ 는 literal $.
    JSON 예시의 {"key": str} 같은 표현은 그대로 유지된다.
    누락 변수는 KeyError 노출 — 호출자가 모든 변수를 명시적으로 넘기게 강제.
    """
    return Template(template).substitute(**variables)
