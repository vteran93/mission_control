from __future__ import annotations

from dataclasses import asdict
from typing import Any

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from config import Settings, apply_settings_overrides
from crew_runtime import AgenticRuntime
from crew_runtime.providers import BedrockProvider, CrewAIProvider, GitHubProvider, OllamaProvider
from database import (
    AgentRunRecord,
    ArtifactRecord,
    OperatorSettingRecord,
    ProjectBlueprintRecord,
    ScrumPlanRecord,
    SprintCycleRecord,
    TaskQueue,
    db,
)


SUPPORTED_OPERATOR_SETTINGS: dict[str, dict[str, Any]] = {
    "ollama.base_url": {"secret": False, "kind": "string"},
    "ollama.default_model": {"secret": False, "kind": "string"},
    "bedrock.region": {"secret": False, "kind": "string"},
    "bedrock.planner_model": {"secret": False, "kind": "string"},
    "bedrock.reviewer_model": {"secret": False, "kind": "string"},
    "bedrock.active_probe": {"secret": False, "kind": "bool"},
    "github.api_url": {"secret": False, "kind": "string"},
    "github.token": {"secret": True, "kind": "string"},
    "github.app_id": {"secret": False, "kind": "int"},
    "github.app_installation_id": {"secret": False, "kind": "int"},
    "github.app_private_key": {"secret": True, "kind": "string"},
    "github.repository": {"secret": False, "kind": "string"},
    "github.default_base_branch": {"secret": False, "kind": "string"},
    "github.protected_branches": {"secret": False, "kind": "string_list"},
    "github.required_approving_review_count": {"secret": False, "kind": "int"},
    "github.dismiss_stale_reviews": {"secret": False, "kind": "bool"},
    "github.require_conversation_resolution": {"secret": False, "kind": "bool"},
}


class OperatorControlService:
    def __init__(self, base_settings: Settings):
        self.base_settings = base_settings

    def build_dashboard(self, app: Flask) -> dict[str, Any]:
        effective_settings = self.build_effective_settings()
        runtime = app.extensions["mission_control_runtime"]
        runtime_health = runtime.healthcheck()
        return {
            "settings": self.serialize_settings(),
            "providers": self._provider_health(effective_settings),
            "runtime": runtime_health["runtime"],
            "queue": runtime_health["queue"],
            "overview": self._overview_metrics(),
            "runtime_config_applied": self._runtime_matches(runtime.settings, effective_settings),
        }

    def serialize_settings(self) -> dict[str, Any]:
        effective_settings = self.build_effective_settings()
        overrides = self._load_override_map()
        return {
            "ollama": {
                "base_url": effective_settings.ollama.base_url,
                "default_model": effective_settings.ollama.default_model,
                "healthcheck_timeout_seconds": effective_settings.ollama.healthcheck_timeout_seconds,
                "overridden_fields": self._overridden_fields("ollama", overrides),
            },
            "bedrock": {
                "region": effective_settings.bedrock.region,
                "planner_model": effective_settings.bedrock.planner_model,
                "reviewer_model": effective_settings.bedrock.reviewer_model,
                "active_probe": effective_settings.bedrock.active_probe,
                "overridden_fields": self._overridden_fields("bedrock", overrides),
            },
            "github": {
                "api_url": effective_settings.github.api_url,
                "repository": effective_settings.github.repository,
                "default_base_branch": effective_settings.github.default_base_branch,
                "protected_branches": list(effective_settings.github.protected_branches),
                "token_configured": bool(effective_settings.github.token),
                "token_overridden": "github.token" in overrides,
                "app_id": effective_settings.github.app_id,
                "app_installation_id": effective_settings.github.app_installation_id,
                "app_private_key_configured": bool(effective_settings.github.app_private_key),
                "required_approving_review_count": effective_settings.github.required_approving_review_count,
                "dismiss_stale_reviews": effective_settings.github.dismiss_stale_reviews,
                "require_conversation_resolution": effective_settings.github.require_conversation_resolution,
                "auth_mode": self._github_auth_mode(effective_settings.github),
                "overridden_fields": self._overridden_fields("github", overrides),
            },
        }

    def update_settings(self, payload: dict[str, Any], *, app: Flask) -> dict[str, Any]:
        updates = self._normalize_payload(payload)
        records = self._load_record_map()

        for key, value in updates.items():
            record = records.get(key)
            if value is None:
                if record is not None:
                    db.session.delete(record)
                continue
            if record is None:
                record = OperatorSettingRecord(
                    key=key,
                    value_json=value,
                    is_secret=bool(SUPPORTED_OPERATOR_SETTINGS[key]["secret"]),
                )
                db.session.add(record)
                continue
            record.value_json = value
            record.is_secret = bool(SUPPORTED_OPERATOR_SETTINGS[key]["secret"])

        db.session.commit()
        self.reload_runtime(app)
        return self.build_dashboard(app)

    def build_effective_settings(self) -> Settings:
        overrides = self._load_overrides()
        return apply_settings_overrides(self.base_settings, **overrides)

    def reload_runtime(self, app: Flask, *, start_dispatcher: bool = True) -> None:
        effective_settings = self.build_effective_settings()
        current_runtime = app.extensions.get("mission_control_runtime")
        if current_runtime is not None:
            current_runtime.stop()

        runtime = AgenticRuntime(effective_settings)
        app.extensions["mission_control_runtime"] = runtime
        app.extensions["queue_dispatcher"] = runtime.dispatcher
        app.config.update(effective_settings.to_flask_config())
        if start_dispatcher:
            runtime.start_background_dispatcher(app)

    def _load_record_map(self) -> dict[str, OperatorSettingRecord]:
        try:
            rows = OperatorSettingRecord.query.order_by(OperatorSettingRecord.key.asc()).all()
        except SQLAlchemyError:
            db.session.rollback()
            return {}
        return {row.key: row for row in rows}

    def _load_override_map(self) -> dict[str, Any]:
        return {key: record.value_json for key, record in self._load_record_map().items()}

    def _load_overrides(self) -> dict[str, dict[str, Any]]:
        overrides: dict[str, dict[str, Any]] = {
            "ollama": {},
            "bedrock": {},
            "github": {},
        }
        for key, value in self._load_override_map().items():
            group, field = key.split(".", 1)
            if key == "github.protected_branches":
                overrides[group][field] = tuple(value or [])
            else:
                overrides[group][field] = value
        return overrides

    @staticmethod
    def _overridden_fields(group: str, overrides: dict[str, Any]) -> list[str]:
        prefix = f"{group}."
        return sorted(
            key[len(prefix):]
            for key in overrides
            if key.startswith(prefix) and key not in {"github.token", "github.app_private_key"}
        )

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for group, fields in payload.items():
            if group not in {"ollama", "bedrock", "github"}:
                raise ValueError(f"Unsupported operator settings group: {group}")
            if not isinstance(fields, dict):
                raise ValueError(f"Operator settings group must be an object: {group}")
            for field, raw_value in fields.items():
                key = f"{group}.{field}"
                if key not in SUPPORTED_OPERATOR_SETTINGS:
                    raise ValueError(f"Unsupported operator setting: {key}")
                normalized[key] = self._normalize_value(key, raw_value)
        return normalized

    @staticmethod
    def _normalize_value(key: str, raw_value: Any) -> Any:
        kind = SUPPORTED_OPERATOR_SETTINGS[key]["kind"]
        if kind == "string":
            if raw_value is None:
                return None
            if not isinstance(raw_value, str):
                raise ValueError(f"Operator setting must be a string: {key}")
            value = raw_value.strip()
            return value or None
        if kind == "bool":
            if isinstance(raw_value, bool):
                return raw_value
            raise ValueError(f"Operator setting must be a boolean: {key}")
        if kind == "string_list":
            if raw_value is None:
                return None
            if isinstance(raw_value, str):
                items = [item.strip() for item in raw_value.split(",") if item.strip()]
                return items or None
            if isinstance(raw_value, list):
                items = [str(item).strip() for item in raw_value if str(item).strip()]
                return items or None
            raise ValueError(f"Operator setting must be a list of strings: {key}")
        if kind == "int":
            if raw_value is None:
                return None
            if isinstance(raw_value, int) and not isinstance(raw_value, bool):
                return raw_value
            if isinstance(raw_value, str) and raw_value.strip():
                return int(raw_value.strip())
            raise ValueError(f"Operator setting must be an integer: {key}")
        raise ValueError(f"Unsupported operator setting kind: {key}")

    @staticmethod
    def _provider_health(settings: Settings) -> dict[str, Any]:
        providers = (
            CrewAIProvider(),
            OllamaProvider(settings.ollama),
            BedrockProvider(settings.bedrock),
            GitHubProvider(settings.github),
        )
        return {
            provider.name: asdict(provider.healthcheck())
            for provider in providers
        }

    @staticmethod
    def _runtime_matches(current_settings: Settings, effective_settings: Settings) -> bool:
        return (
            current_settings.ollama == effective_settings.ollama
            and current_settings.bedrock == effective_settings.bedrock
            and current_settings.github == effective_settings.github
        )

    @staticmethod
    def _github_auth_mode(github_settings) -> str:
        if (
            github_settings.app_id is not None
            and github_settings.app_installation_id is not None
            and github_settings.app_private_key
        ):
            return "app"
        if github_settings.token:
            return "token"
        return "none"

    @staticmethod
    def _overview_metrics() -> dict[str, int]:
        return {
            "blueprints": ProjectBlueprintRecord.query.count(),
            "scrum_plans": ScrumPlanRecord.query.count(),
            "active_sprints": SprintCycleRecord.query.filter_by(status="active").count(),
            "blocked_sprints": SprintCycleRecord.query.filter_by(status="blocked").count(),
            "agent_runs": AgentRunRecord.query.count(),
            "artifacts": ArtifactRecord.query.count(),
            "queued_messages": TaskQueue.query.filter(
                TaskQueue.status.in_(("pending", "processing"))
            ).count(),
        }
