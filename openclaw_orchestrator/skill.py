"""Skill registration helpers for OpenClaw/ClawHub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class SkillDefinition:
    """Metadata required to register a skill within ClawHub."""

    name: str
    description: str
    entrypoint: str
    models: Mapping[str, str]
    config_schema: Mapping[str, Any]


def build_skill_definition() -> SkillDefinition:
    """Construct the ClawHub skill definition for this orchestrator."""

    return SkillDefinition(
        name="mission-control-orchestrator",
        description=(
            "LangGraph supervisor-worker orchestrator wired to OpenClaw local state."
        ),
        entrypoint="openclaw_orchestrator.graph:build_app",
        models={
            "supervisor": "gemini-flash",
            "developer": "claude-3.5-sonnet",
            "qa": "claude-3.5-haiku",
        },
        config_schema={
            "OPENCLAW_STATE_DIR": {
                "type": "string",
                "description": "Path to .openclaw/state directory",
            },
            "OPENCLAW_SQLITE_PATH": {
                "type": "string",
                "description": "Path to sqlite checkpoint file",
            },
        },
    )


def register_skill(
    registry: Callable[[Mapping[str, Any]], None]
) -> Mapping[str, Any]:
    """Register the orchestrator as a ClawHub skill.

    The registry callback is provided by ClawHub/OpenClaw runtime.
    """

    definition = build_skill_definition()
    payload = {
        "name": definition.name,
        "description": definition.description,
        "entrypoint": definition.entrypoint,
        "models": dict(definition.models),
        "config_schema": dict(definition.config_schema),
    }
    registry(payload)
    return payload
