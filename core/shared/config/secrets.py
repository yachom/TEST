"""SecretProvider — 환경변수 / Airflow Variables / Vault / Cloud Secrets 흡수 자리.

확장 자리. 현재는 EnvSecretProvider 만 — 기존 os.environ.get() 동작 보존.

설계 의도:
  LLMSettings.api_key, _build_naver_credentials() 등 키 사용처가 직접 os.environ
  대신 SecretProvider 인터페이스를 호출하면, 환경별 자동 분기 가능:
    - 로컬:   EnvSecretProvider (.env + os.environ)
    - Airflow: AirflowVariableSecretProvider (Variable.get + Connections)
    - K8s:    EnvSecretProvider (env var 주입)
    - prod:   ChainSecretProvider([AwsSecretsProvider, VaultProvider, EnvProvider])

POC 시점에서는 EnvSecretProvider 한 가지로 현재 동작과 동일하게 유지.
실제 코드 마이그레이션 (os.environ.get → secrets.get) 은 점진적으로.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional


class SecretProvider(ABC):
    """비밀 / API 키 / 설정값 의 추상 조회."""

    @abstractmethod
    def get(self, key: str, default: str = "") -> str:
        """키에 해당하는 값을 반환. 없거나 빈 값이면 default."""


class EnvSecretProvider(SecretProvider):
    """기본 — os.environ 에서 조회. .env 는 CLI 진입점에서 로드됨 (cli.py 참조)."""

    def get(self, key: str, default: str = "") -> str:
        value = os.environ.get(key, default)
        if value is None:
            return default
        return value


class ChainSecretProvider(SecretProvider):
    """여러 provider 를 순서대로 시도. 첫 빈 문자열 아닌 값 반환.

    사용 예: ChainSecretProvider([AirflowProvider, AwsProvider, EnvProvider])
    """

    def __init__(self, providers: list[SecretProvider]) -> None:
        if not providers:
            raise ValueError("ChainSecretProvider requires at least one provider")
        self._providers = providers

    def get(self, key: str, default: str = "") -> str:
        for p in self._providers:
            value = p.get(key, default="")
            if value:
                return value
        return default


class StaticSecretProvider(SecretProvider):
    """테스트용 — dict 에서 조회."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, key: str, default: str = "") -> str:
        return self._values.get(key, default)
