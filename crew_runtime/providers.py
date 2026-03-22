from __future__ import annotations

import importlib.util
import sys

import requests

from config import BedrockSettings, GitHubSettings, OllamaSettings

from .contracts import ProviderHealth


class CrewAIProvider:
    name = "crewai"

    def healthcheck(self) -> ProviderHealth:
        try:
            available = importlib.util.find_spec("crewai") is not None
        except ValueError:
            available = "crewai" in sys.modules
        detail = "CrewAI import disponible" if available else "CrewAI no esta instalado en el entorno"
        return ProviderHealth(
            name=self.name,
            ok=available,
            configured=True,
            detail=detail,
        )


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: OllamaSettings):
        self.settings = settings

    def healthcheck(self) -> ProviderHealth:
        endpoint = f"{self.settings.base_url.rstrip('/')}/api/tags"
        try:
            response = requests.get(
                endpoint,
                timeout=self.settings.healthcheck_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            return ProviderHealth(
                name=self.name,
                ok=False,
                configured=bool(self.settings.base_url),
                detail=f"Ollama no responde: {exc}",
                metadata={"base_url": self.settings.base_url},
            )

        models = payload.get("models", [])
        return ProviderHealth(
            name=self.name,
            ok=True,
            configured=True,
            detail="Ollama disponible",
            metadata={
                "base_url": self.settings.base_url,
                "default_model": self.settings.default_model,
                "model_count": len(models),
            },
        )


class BedrockProvider:
    name = "bedrock"

    def __init__(self, settings: BedrockSettings):
        self.settings = settings

    def healthcheck(self) -> ProviderHealth:
        if not self.settings.region:
            return ProviderHealth(
                name=self.name,
                ok=False,
                configured=False,
                detail="BEDROCK_REGION o AWS_REGION no configurado",
            )

        boto3_available = importlib.util.find_spec("boto3") is not None
        if not boto3_available:
            return ProviderHealth(
                name=self.name,
                ok=False,
                configured=True,
                detail="Configuracion Bedrock detectada, pero boto3 no esta instalado",
                metadata={"region": self.settings.region},
            )

        detail = "Configuracion Bedrock cargada"
        if self.settings.active_probe:
            detail = "Configuracion Bedrock cargada; probe remoto se habilitara en runtime posterior"
        return ProviderHealth(
            name=self.name,
            ok=True,
            configured=True,
            detail=detail,
            metadata={
                "region": self.settings.region,
                "planner_model": self.settings.planner_model,
                "reviewer_model": self.settings.reviewer_model,
            },
        )


class GitHubProvider:
    name = "github"

    def __init__(self, settings: GitHubSettings):
        self.settings = settings

    def healthcheck(self) -> ProviderHealth:
        if not self.settings.token:
            return ProviderHealth(
                name=self.name,
                ok=False,
                configured=False,
                detail="GITHUB_TOKEN no configurado",
                metadata={"repository": self.settings.repository},
            )

        try:
            response = requests.get(
                f"{self.settings.api_url.rstrip('/')}/rate_limit",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.settings.token}",
                },
                timeout=5,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return ProviderHealth(
                name=self.name,
                ok=False,
                configured=True,
                detail=f"GitHub no responde: {exc}",
                metadata={"repository": self.settings.repository},
            )

        return ProviderHealth(
            name=self.name,
            ok=True,
            configured=True,
            detail="GitHub disponible",
            metadata={
                "api_url": self.settings.api_url,
                "repository": self.settings.repository,
                "default_base_branch": self.settings.default_base_branch,
            },
        )
