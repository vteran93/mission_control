from __future__ import annotations

from dataclasses import dataclass

from config import Settings


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: str
    model: str
    temperature: float = 0.1
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    base_url: str | None = None
    aws_region_name: str | None = None
    routing_reason: str = ""

    def to_llm_kwargs(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.timeout_seconds is not None:
            payload["timeout"] = self.timeout_seconds
        if self.base_url:
            payload["base_url"] = self.base_url
        if self.aws_region_name:
            payload["aws_region_name"] = self.aws_region_name
        return payload

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "base_url": self.base_url,
            "aws_region_name": self.aws_region_name,
            "routing_reason": self.routing_reason,
        }


class ModelRegistry:
    """Seed model profiles for CrewAI dispatch routing."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._profiles = self._build_profiles()

    def _build_profiles(self) -> dict[str, ModelProfile]:
        profiles = {
            "worker_local": ModelProfile(
                name="worker_local",
                provider="ollama",
                model=f"ollama/{self.settings.ollama.default_model}",
                base_url=self.settings.ollama.base_url,
                temperature=0.1,
                max_tokens=self.settings.runtime.llm_max_tokens,
                timeout_seconds=self.settings.runtime.llm_timeout_seconds,
                routing_reason="Default local worker profile for coding and execution.",
            )
        }

        if self.settings.bedrock.region and self.settings.bedrock.planner_model:
            profiles["planner_bedrock"] = ModelProfile(
                name="planner_bedrock",
                provider="bedrock",
                model=f"bedrock/{self.settings.bedrock.planner_model}",
                aws_region_name=self.settings.bedrock.region,
                temperature=0.1,
                max_tokens=self.settings.runtime.llm_max_tokens,
                timeout_seconds=self.settings.runtime.llm_timeout_seconds,
                routing_reason="Bedrock planner/orchestrator profile for PM decisions.",
            )

        if self.settings.bedrock.region and self.settings.bedrock.reviewer_model:
            profiles["reviewer_bedrock"] = ModelProfile(
                name="reviewer_bedrock",
                provider="bedrock",
                model=f"bedrock/{self.settings.bedrock.reviewer_model}",
                aws_region_name=self.settings.bedrock.region,
                temperature=0.1,
                max_tokens=self.settings.runtime.llm_max_tokens,
                timeout_seconds=self.settings.runtime.llm_timeout_seconds,
                routing_reason="Bedrock reviewer profile for QA and escalations.",
            )

        return profiles

    @property
    def profiles(self) -> dict[str, ModelProfile]:
        return dict(self._profiles)

    def resolve_profile(self, target_agent: str) -> ModelProfile:
        label = target_agent.strip().lower()
        if label == "jarvis-pm":
            return self._profiles.get("planner_bedrock", self._profiles["worker_local"])
        if label == "jarvis-qa":
            return self._profiles.get("reviewer_bedrock", self._profiles["worker_local"])
        return self._profiles["worker_local"]

    def resolve_dispatch_profiles(
        self,
        target_agent: str,
        *,
        retry_count: int = 0,
    ) -> list[ModelProfile]:
        primary = self.resolve_profile(target_agent)
        fallback = self._resolve_escalation_profile(target_agent)

        if (
            retry_count >= self.settings.runtime.dispatcher_escalate_after_retries
            and fallback is not None
            and fallback.name != primary.name
        ):
            primary, fallback = fallback, self._profiles["worker_local"]

        ordered_profiles: list[ModelProfile] = [primary]
        if (
            self.settings.runtime.dispatcher_enable_fallback
            and fallback is not None
            and fallback.name != primary.name
        ):
            ordered_profiles.append(fallback)

        deduped_profiles: list[ModelProfile] = []
        seen_names: set[str] = set()
        for profile in ordered_profiles:
            if profile.name in seen_names:
                continue
            deduped_profiles.append(profile)
            seen_names.add(profile.name)
        return deduped_profiles

    def _resolve_escalation_profile(self, target_agent: str) -> ModelProfile | None:
        label = target_agent.strip().lower()
        if label == "jarvis-pm":
            return self._profiles.get("planner_bedrock")
        if label == "jarvis-qa":
            return self._profiles.get("reviewer_bedrock") or self._profiles.get("planner_bedrock")
        return self._profiles.get("reviewer_bedrock") or self._profiles.get("planner_bedrock")

    def describe(self) -> dict[str, object]:
        return {
            "profiles": {name: profile.to_dict() for name, profile in self._profiles.items()},
            "routing_defaults": {
                "jarvis-dev": self.resolve_profile("jarvis-dev").name,
                "jarvis-pm": self.resolve_profile("jarvis-pm").name,
                "jarvis-qa": self.resolve_profile("jarvis-qa").name,
            },
            "escalation_defaults": {
                "jarvis-dev": [
                    profile.name
                    for profile in self.resolve_dispatch_profiles("jarvis-dev")
                ],
                "jarvis-pm": [
                    profile.name
                    for profile in self.resolve_dispatch_profiles("jarvis-pm")
                ],
                "jarvis-qa": [
                    profile.name
                    for profile in self.resolve_dispatch_profiles("jarvis-qa")
                ],
            },
            "runtime_policy": {
                "escalate_after_retries": self.settings.runtime.dispatcher_escalate_after_retries,
                "fallback_enabled": self.settings.runtime.dispatcher_enable_fallback,
                "llm_timeout_seconds": self.settings.runtime.llm_timeout_seconds,
                "llm_max_tokens": self.settings.runtime.llm_max_tokens,
            },
        }
