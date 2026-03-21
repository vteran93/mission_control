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
    )
