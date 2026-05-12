from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RUNTIME_PATH = _ROOT / "config" / "runtime.yaml"


@dataclass(frozen=True)
class DatabaseSettings:
    url: str
    schema_version: int = 1


@dataclass(frozen=True)
class LLMSettings:
    role: str = "default"
    provider: str = "stub"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_seconds: float = 60.0

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass(frozen=True)
class ObservabilitySettings:
    """observability 백엔드 선택 및 자격증명 위치.

    backend:
      noop     — 기본값. 외부 호출 0.
      stdout   — JSON line 로깅 (로컬 디버깅).
      langfuse — Langfuse Cloud / Self-hosted.

    langfuse_* env 변수는 키 자체 가 아니라 키가 저장된 환경변수 이름.
    """
    backend: str = "noop"
    langfuse_public_key_env: str = "LANGFUSE_PUBLIC_KEY"
    langfuse_secret_key_env: str = "LANGFUSE_SECRET_KEY"
    langfuse_host: str = "https://cloud.langfuse.com"
    stdout_include_prompts: bool = False

    @property
    def langfuse_public_key(self) -> str:
        return os.environ.get(self.langfuse_public_key_env, "")

    @property
    def langfuse_secret_key(self) -> str:
        return os.environ.get(self.langfuse_secret_key_env, "")


@dataclass(frozen=True)
class RuntimeSettings:
    database: DatabaseSettings
    llm: LLMSettings
    llm_roles: dict[str, LLMSettings]
    observability: ObservabilitySettings

    def llm_for(self, role: str) -> LLMSettings:
        return self.llm_roles.get(role, self.llm)


def load_runtime_settings(path: str | Path | None = None) -> RuntimeSettings:
    config_path = Path(path) if path else _DEFAULT_RUNTIME_PATH
    raw = _read_yaml(config_path)

    db_raw = raw.get("database", {})
    llm_raw = raw.get("llm", {})

    database = DatabaseSettings(
        url=os.environ.get("FNPRICING_DATABASE_URL", db_raw.get("url", "sqlite:///./var/fnpricing.db")),
        schema_version=int(os.environ.get("FNPRICING_SCHEMA_VERSION", db_raw.get("schema_version", 1))),
    )
    default_llm = _build_default_llm_settings(llm_raw)
    role_settings = _build_role_llm_settings(llm_raw, default_llm)
    observability = _build_observability_settings(raw.get("observability", {}) or {})
    return RuntimeSettings(
        database=database,
        llm=default_llm,
        llm_roles=role_settings,
        observability=observability,
    )


def _build_observability_settings(raw: dict[str, Any]) -> ObservabilitySettings:
    lf_raw = raw.get("langfuse", {}) or {}
    return ObservabilitySettings(
        backend=os.environ.get(
            "FNPRICING_OBSERVABILITY_BACKEND", raw.get("backend", "noop")
        ).lower(),
        langfuse_public_key_env=lf_raw.get("public_key_env", "LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key_env=lf_raw.get("secret_key_env", "LANGFUSE_SECRET_KEY"),
        langfuse_host=os.environ.get(
            "LANGFUSE_HOST", lf_raw.get("host", "https://cloud.langfuse.com")
        ),
        stdout_include_prompts=bool(
            os.environ.get(
                "FNPRICING_OBSERVABILITY_STDOUT_INCLUDE_PROMPTS",
                raw.get("stdout_include_prompts", False),
            )
        ),
    )


def _build_default_llm_settings(raw: dict[str, Any]) -> LLMSettings:
    default_raw = raw.get("default", raw)
    return LLMSettings(
        role="default",
        provider=os.environ.get("FNPRICING_LLM_PROVIDER", default_raw.get("provider", "stub")),
        model=os.environ.get("FNPRICING_LLM_MODEL", default_raw.get("model", "gpt-4o-mini")),
        api_key_env=os.environ.get("FNPRICING_LLM_API_KEY_ENV", default_raw.get("api_key_env", "OPENAI_API_KEY")),
        temperature=float(os.environ.get("FNPRICING_LLM_TEMPERATURE", default_raw.get("temperature", 0.0))),
        max_tokens=int(os.environ.get("FNPRICING_LLM_MAX_TOKENS", default_raw.get("max_tokens", 2048))),
        timeout_seconds=float(os.environ.get("FNPRICING_LLM_TIMEOUT_SECONDS", default_raw.get("timeout_seconds", 60))),
    )


def _build_role_llm_settings(raw: dict[str, Any], default: LLMSettings) -> dict[str, LLMSettings]:
    roles_raw = raw.get("roles", {})
    result: dict[str, LLMSettings] = {}
    for role, role_raw in roles_raw.items():
        env_prefix = f"FNPRICING_LLM_{role.upper()}_"
        result[role] = LLMSettings(
            role=role,
            provider=os.environ.get(f"{env_prefix}PROVIDER", role_raw.get("provider", default.provider)),
            model=os.environ.get(f"{env_prefix}MODEL", role_raw.get("model", default.model)),
            api_key_env=os.environ.get(f"{env_prefix}API_KEY_ENV", role_raw.get("api_key_env", default.api_key_env)),
            temperature=float(os.environ.get(f"{env_prefix}TEMPERATURE", role_raw.get("temperature", default.temperature))),
            max_tokens=int(os.environ.get(f"{env_prefix}MAX_TOKENS", role_raw.get("max_tokens", default.max_tokens))),
            timeout_seconds=float(os.environ.get(f"{env_prefix}TIMEOUT_SECONDS", role_raw.get("timeout_seconds", default.timeout_seconds))),
        )
    return result


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded or {}
