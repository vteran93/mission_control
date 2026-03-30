from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_FORBIDDEN_PATH_PREFIXES = (
    ".git/",
    ".venv/",
    "node_modules/",
    "runtime/",
    "instance/",
    "logs/",
    "__pycache__/",
)
DEFAULT_FORBIDDEN_PATH_GLOBS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "secrets/*",
    ".aws/*",
)
DEFAULT_FORBIDDEN_COMMAND_PATTERNS = (
    "rm -rf",
    "git reset --hard",
    "git checkout --",
    "sudo ",
    "chmod -r",
    "chown ",
    "mkfs",
    "dd if=",
    ":(){",
)
DEFAULT_POLICY_RELATIVE_PATH = ".mission_control/guardrails/architecture_guardrails.json"


class ArchitectureGuardrailViolation(ValueError):
    """Raised when a path or command violates the active architecture policy."""


@dataclass(frozen=True)
class ArchitectureGuardrailPolicy:
    scope: dict[str, Any]
    allowed_write_paths: tuple[str, ...]
    allowed_write_roots: tuple[str, ...]
    forbidden_path_prefixes: tuple[str, ...] = DEFAULT_FORBIDDEN_PATH_PREFIXES
    forbidden_path_globs: tuple[str, ...] = DEFAULT_FORBIDDEN_PATH_GLOBS
    forbidden_command_patterns: tuple[str, ...] = DEFAULT_FORBIDDEN_COMMAND_PATTERNS

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "allowed_write_paths": list(self.allowed_write_paths),
            "allowed_write_roots": list(self.allowed_write_roots),
            "forbidden_path_prefixes": list(self.forbidden_path_prefixes),
            "forbidden_path_globs": list(self.forbidden_path_globs),
            "forbidden_command_patterns": list(self.forbidden_command_patterns),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArchitectureGuardrailPolicy":
        return cls(
            scope=dict(payload.get("scope") or {}),
            allowed_write_paths=tuple(
                normalize_relative_path(path)
                for path in payload.get("allowed_write_paths") or []
            ),
            allowed_write_roots=tuple(
                ensure_root_suffix(normalize_relative_path(path))
                for path in payload.get("allowed_write_roots") or []
            ),
            forbidden_path_prefixes=tuple(
                ensure_root_suffix(normalize_relative_path(path))
                for path in payload.get("forbidden_path_prefixes") or DEFAULT_FORBIDDEN_PATH_PREFIXES
            ),
            forbidden_path_globs=tuple(payload.get("forbidden_path_globs") or DEFAULT_FORBIDDEN_PATH_GLOBS),
            forbidden_command_patterns=tuple(
                payload.get("forbidden_command_patterns") or DEFAULT_FORBIDDEN_COMMAND_PATTERNS
            ),
        )


def normalize_relative_path(raw_path: str | Path) -> str:
    normalized = Path(str(raw_path).replace("\\", "/"))
    if normalized.is_absolute():
        raise ArchitectureGuardrailViolation(f"Guardrail paths must be relative: {raw_path}")
    parts = [part for part in normalized.parts if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise ArchitectureGuardrailViolation(f"Guardrail path escapes workspace root: {raw_path}")
    return "/".join(parts)


def ensure_root_suffix(raw_path: str) -> str:
    return raw_path if raw_path.endswith("/") else raw_path + "/"


def validate_relative_path(relative_path: str | Path, policy: ArchitectureGuardrailPolicy) -> str:
    normalized = normalize_relative_path(relative_path)
    prefixed_path = ensure_root_suffix(normalized) if normalized else normalized

    for forbidden_prefix in policy.forbidden_path_prefixes:
        if normalized == forbidden_prefix.rstrip("/") or normalized.startswith(forbidden_prefix):
            raise ArchitectureGuardrailViolation(
                f"Path blocked by architecture guardrails: {normalized}"
            )

    for forbidden_glob in policy.forbidden_path_globs:
        if fnmatch.fnmatch(normalized, forbidden_glob):
            raise ArchitectureGuardrailViolation(
                f"Path blocked by architecture guardrails: {normalized}"
            )

    if normalized in policy.allowed_write_paths:
        return normalized

    if any(prefixed_path.startswith(root) or normalized.startswith(root) for root in policy.allowed_write_roots):
        return normalized

    raise ArchitectureGuardrailViolation(
        f"Path not allowed by architecture guardrails: {normalized}"
    )


def assert_allowed_paths(
    relative_paths: list[str] | tuple[str, ...],
    policy: ArchitectureGuardrailPolicy,
) -> None:
    for relative_path in relative_paths:
        validate_relative_path(relative_path, policy)


def validate_unix_command(command: str, policy: ArchitectureGuardrailPolicy | None = None) -> str:
    normalized = " ".join(command.strip().lower().split())
    patterns = (
        policy.forbidden_command_patterns
        if policy is not None
        else DEFAULT_FORBIDDEN_COMMAND_PATTERNS
    )
    for pattern in patterns:
        if pattern in normalized:
            raise ArchitectureGuardrailViolation(
                f"Command blocked by runtime guardrails: {command}"
            )
    return normalized


def load_guardrail_policy(workspace_root: str | Path) -> ArchitectureGuardrailPolicy | None:
    root = Path(workspace_root).expanduser().resolve()
    policy_path = root / DEFAULT_POLICY_RELATIVE_PATH
    if not policy_path.is_file():
        return None
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    return ArchitectureGuardrailPolicy.from_dict(payload)


def find_guardrail_policy(
    start_path: str | Path,
    *,
    stop_path: str | Path | None = None,
) -> tuple[Path, ArchitectureGuardrailPolicy] | None:
    current = Path(start_path).expanduser().resolve()
    if current.is_file():
        current = current.parent
    stop = Path(stop_path).expanduser().resolve() if stop_path is not None else None

    while True:
        policy = load_guardrail_policy(current)
        if policy is not None:
            return current, policy
        if stop is not None and current == stop:
            break
        if current.parent == current:
            break
        current = current.parent
    return None


def save_guardrail_policy(
    workspace_root: str | Path,
    policy: ArchitectureGuardrailPolicy,
) -> Path:
    root = Path(workspace_root).expanduser().resolve()
    policy_path = root / DEFAULT_POLICY_RELATIVE_PATH
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(policy.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return policy_path


def merge_project_guardrails(
    policy: ArchitectureGuardrailPolicy,
    project_guardrails: dict[str, Any] | None,
) -> ArchitectureGuardrailPolicy:
    if not isinstance(project_guardrails, dict) or not project_guardrails:
        return policy

    runtime_guardrails = project_guardrails.get("runtime")
    if not isinstance(runtime_guardrails, dict):
        runtime_guardrails = project_guardrails

    forbidden_path_prefixes = list(policy.forbidden_path_prefixes)
    forbidden_path_globs = list(policy.forbidden_path_globs)
    forbidden_command_patterns = list(policy.forbidden_command_patterns)

    for raw_prefix in runtime_guardrails.get("protected_path_prefixes", []) or []:
        normalized = ensure_root_suffix(normalize_relative_path(raw_prefix))
        if normalized not in forbidden_path_prefixes:
            forbidden_path_prefixes.append(normalized)

    for raw_prefix in runtime_guardrails.get("forbidden_path_prefixes", []) or []:
        normalized = ensure_root_suffix(normalize_relative_path(raw_prefix))
        if normalized not in forbidden_path_prefixes:
            forbidden_path_prefixes.append(normalized)

    for raw_glob in runtime_guardrails.get("protected_files", []) or []:
        normalized = normalize_relative_path(raw_glob)
        if normalized not in forbidden_path_globs:
            forbidden_path_globs.append(normalized)

    for raw_glob in runtime_guardrails.get("forbidden_path_globs", []) or []:
        normalized = str(raw_glob).strip()
        if normalized and normalized not in forbidden_path_globs:
            forbidden_path_globs.append(normalized)

    for raw_pattern in runtime_guardrails.get("forbidden_command_patterns", []) or []:
        normalized = " ".join(str(raw_pattern).strip().lower().split())
        if normalized and normalized not in forbidden_command_patterns:
            forbidden_command_patterns.append(normalized)

    return ArchitectureGuardrailPolicy.from_dict(
        {
            "scope": policy.scope,
            "allowed_write_paths": list(policy.allowed_write_paths),
            "allowed_write_roots": list(policy.allowed_write_roots),
            "forbidden_path_prefixes": forbidden_path_prefixes,
            "forbidden_path_globs": forbidden_path_globs,
            "forbidden_command_patterns": forbidden_command_patterns,
        }
    )
