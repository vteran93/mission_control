from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_AGENT_LABELS = ("jarvis-pm", "jarvis-dev", "jarvis-qa")


def _as_bool(raw_value: str | None, default: bool = False) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(raw_value: str | None, default: int) -> int:
    if raw_value is None:
        return default
    return int(raw_value)


def _as_float(raw_value: str | None, default: float) -> float:
    if raw_value is None:
        return default
    return float(raw_value)


@dataclass(frozen=True)
class RuntimeSettings:
    enabled: bool
    dispatcher_autostart: bool
    dispatcher_poll_interval_seconds: float
    dispatcher_batch_size: int
    dispatcher_executor: str
    dispatcher_recover_after_seconds: float
    dispatcher_escalate_after_retries: int
    dispatcher_enable_fallback: bool
    llm_timeout_seconds: float
    llm_max_tokens: int
    enable_legacy_bridge: bool
    legacy_gateway_url: str
    legacy_gateway_token: str | None


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    default_model: str
    healthcheck_timeout_seconds: float


@dataclass(frozen=True)
class BedrockSettings:
    region: str | None
    planner_model: str
    reviewer_model: str
    active_probe: bool


@dataclass(frozen=True)
class GitHubSettings:
    api_url: str
    token: str | None
    repository: str | None
    default_base_branch: str


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    instance_path: Path
    runtime_dir: Path
    queue_dir: Path
    heartbeat_lock_dir: Path
    heartbeat_script_dir: Path
    database_url: str
    host: str
    port: int
    debug: bool
    enable_agent_wakeups: bool
    api_base_url: str
    alembic_ini_path: Path
    runtime: RuntimeSettings
    ollama: OllamaSettings
    bedrock: BedrockSettings
    github: GitHubSettings
    supported_agent_labels: tuple[str, ...] = DEFAULT_AGENT_LABELS

    def to_flask_config(self) -> dict[str, Any]:
        return {
            "SQLALCHEMY_DATABASE_URI": self.database_url,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "MISSION_CONTROL_BASE_DIR": str(self.base_dir),
            "MISSION_CONTROL_INSTANCE_PATH": str(self.instance_path),
            "MISSION_CONTROL_RUNTIME_DIR": str(self.runtime_dir),
            "MISSION_CONTROL_QUEUE_DIR": str(self.queue_dir),
            "MISSION_CONTROL_HEARTBEAT_LOCK_DIR": str(self.heartbeat_lock_dir),
            "MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR": str(self.heartbeat_script_dir),
            "MISSION_CONTROL_API_URL": self.api_base_url,
            "ALEMBIC_INI_PATH": str(self.alembic_ini_path),
            "SUPPORTED_AGENT_LABELS": self.supported_agent_labels,
            "ENABLE_AGENT_WAKEUPS": self.enable_agent_wakeups,
            "MISSION_CONTROL_RUNTIME_SETTINGS": self.runtime,
            "MISSION_CONTROL_OLLAMA_SETTINGS": self.ollama,
            "MISSION_CONTROL_BEDROCK_SETTINGS": self.bedrock,
            "MISSION_CONTROL_GITHUB_SETTINGS": self.github,
            "MISSION_CONTROL_RUNTIME_ENABLED": self.runtime.enabled,
            "MISSION_CONTROL_DISPATCHER_AUTOSTART": self.runtime.dispatcher_autostart,
            "MISSION_CONTROL_DISPATCHER_POLL_INTERVAL_SECONDS": self.runtime.dispatcher_poll_interval_seconds,
            "MISSION_CONTROL_DISPATCHER_BATCH_SIZE": self.runtime.dispatcher_batch_size,
            "MISSION_CONTROL_DISPATCHER_EXECUTOR": self.runtime.dispatcher_executor,
            "MISSION_CONTROL_DISPATCHER_RECOVER_AFTER_SECONDS": self.runtime.dispatcher_recover_after_seconds,
            "MISSION_CONTROL_DISPATCHER_ESCALATE_AFTER_RETRIES": self.runtime.dispatcher_escalate_after_retries,
            "MISSION_CONTROL_DISPATCHER_ENABLE_FALLBACK": self.runtime.dispatcher_enable_fallback,
            "MISSION_CONTROL_ENABLE_LEGACY_BRIDGE": self.runtime.enable_legacy_bridge,
            "MISSION_CONTROL_LEGACY_GATEWAY_URL": self.runtime.legacy_gateway_url,
            "MISSION_CONTROL_LLM_TIMEOUT_SECONDS": self.runtime.llm_timeout_seconds,
            "MISSION_CONTROL_LLM_MAX_TOKENS": self.runtime.llm_max_tokens,
            "OLLAMA_BASE_URL": self.ollama.base_url,
            "OLLAMA_DEFAULT_MODEL": self.ollama.default_model,
            "OLLAMA_HEALTHCHECK_TIMEOUT_SECONDS": self.ollama.healthcheck_timeout_seconds,
            "BEDROCK_REGION": self.bedrock.region,
            "BEDROCK_PLANNER_MODEL": self.bedrock.planner_model,
            "BEDROCK_REVIEWER_MODEL": self.bedrock.reviewer_model,
            "MISSION_CONTROL_BEDROCK_ACTIVE_PROBE": self.bedrock.active_probe,
            "GITHUB_API_URL": self.github.api_url,
            "GITHUB_REPOSITORY": self.github.repository,
            "GITHUB_DEFAULT_BASE_BRANCH": self.github.default_base_branch,
            "HOST": self.host,
            "PORT": self.port,
            "DEBUG": self.debug,
        }


def load_settings(base_dir: str | Path | None = None) -> Settings:
    resolved_base_dir = Path(base_dir or os.getenv("MISSION_CONTROL_BASE_DIR") or Path(__file__).resolve().parent)
    instance_path = Path(os.getenv("MISSION_CONTROL_INSTANCE_PATH", resolved_base_dir / "instance"))
    runtime_dir = Path(os.getenv("MISSION_CONTROL_RUNTIME_DIR", resolved_base_dir / "runtime"))
    queue_dir = Path(os.getenv("MISSION_CONTROL_QUEUE_DIR", runtime_dir / "message_queue"))
    heartbeat_lock_dir = Path(
        os.getenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", runtime_dir / "locks")
    )
    heartbeat_script_dir = Path(
        os.getenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", resolved_base_dir / "scripts")
    )
    port = int(os.getenv("PORT", "5001"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = _as_bool(os.getenv("FLASK_DEBUG"), default=True)
    database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(instance_path / 'mission_control.db').resolve()}",
    )
    api_base_url = os.getenv("MISSION_CONTROL_API_URL", f"http://localhost:{port}/api")
    alembic_ini_path = Path(os.getenv("ALEMBIC_INI_PATH", resolved_base_dir / "alembic.ini"))
    runtime = RuntimeSettings(
        enabled=_as_bool(os.getenv("MISSION_CONTROL_RUNTIME_ENABLED"), default=True),
        dispatcher_autostart=_as_bool(
            os.getenv("MISSION_CONTROL_DISPATCHER_AUTOSTART"),
            default=False,
        ),
        dispatcher_poll_interval_seconds=_as_float(
            os.getenv("MISSION_CONTROL_DISPATCHER_POLL_INTERVAL_SECONDS"),
            default=5.0,
        ),
        dispatcher_batch_size=_as_int(
            os.getenv("MISSION_CONTROL_DISPATCHER_BATCH_SIZE"),
            default=5,
        ),
        dispatcher_executor=os.getenv("MISSION_CONTROL_DISPATCHER_EXECUTOR", "disabled"),
        dispatcher_recover_after_seconds=_as_float(
            os.getenv("MISSION_CONTROL_DISPATCHER_RECOVER_AFTER_SECONDS"),
            default=900.0,
        ),
        dispatcher_escalate_after_retries=_as_int(
            os.getenv("MISSION_CONTROL_DISPATCHER_ESCALATE_AFTER_RETRIES"),
            default=1,
        ),
        dispatcher_enable_fallback=_as_bool(
            os.getenv("MISSION_CONTROL_DISPATCHER_ENABLE_FALLBACK"),
            default=True,
        ),
        llm_timeout_seconds=_as_float(
            os.getenv("MISSION_CONTROL_LLM_TIMEOUT_SECONDS"),
            default=180.0,
        ),
        llm_max_tokens=_as_int(
            os.getenv("MISSION_CONTROL_LLM_MAX_TOKENS"),
            default=2048,
        ),
        enable_legacy_bridge=_as_bool(
            os.getenv("MISSION_CONTROL_ENABLE_LEGACY_BRIDGE"),
            default=False,
        ),
        legacy_gateway_url=os.getenv("MISSION_CONTROL_LEGACY_GATEWAY_URL", "http://127.0.0.1:18789"),
        legacy_gateway_token=os.getenv("CLAWDBOT_GATEWAY_TOKEN"),
    )
    ollama = OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        default_model=os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:latest"),
        healthcheck_timeout_seconds=_as_float(
            os.getenv("OLLAMA_HEALTHCHECK_TIMEOUT_SECONDS"),
            default=3.0,
        ),
    )
    bedrock = BedrockSettings(
        region=os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION"),
        planner_model=os.getenv("BEDROCK_PLANNER_MODEL", ""),
        reviewer_model=os.getenv("BEDROCK_REVIEWER_MODEL", ""),
        active_probe=_as_bool(
            os.getenv("MISSION_CONTROL_BEDROCK_ACTIVE_PROBE"),
            default=False,
        ),
    )
    github = GitHubSettings(
        api_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
        token=os.getenv("GITHUB_TOKEN"),
        repository=os.getenv("GITHUB_REPOSITORY"),
        default_base_branch=os.getenv("GITHUB_DEFAULT_BASE_BRANCH", "main"),
    )

    return Settings(
        base_dir=resolved_base_dir,
        instance_path=instance_path,
        runtime_dir=runtime_dir,
        queue_dir=queue_dir,
        heartbeat_lock_dir=heartbeat_lock_dir,
        heartbeat_script_dir=heartbeat_script_dir,
        database_url=database_url,
        host=host,
        port=port,
        debug=debug,
        enable_agent_wakeups=_as_bool(
            os.getenv("ENABLE_AGENT_WAKEUPS"),
            default=False,
        ),
        api_base_url=api_base_url,
        alembic_ini_path=alembic_ini_path,
        runtime=runtime,
        ollama=ollama,
        bedrock=bedrock,
        github=github,
    )
