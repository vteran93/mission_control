#!/usr/bin/env python3
"""Standalone installer for the Mission Control OpenClaw orchestrator skill.

This script is intentionally non-interactive and idempotent to enable
"minimal-human-intervention" installs in CI, servers, or local workstations.

What it does:
1. Installs Python dependencies from `requirements.txt` (optional).
2. Copies `openclaw_orchestrator/` into a target skills directory.
3. Generates `skill_manifest.json` and `.env` files for runtime wiring.
4. Runs a lightweight import smoke test.

Example:
    python3 scripts/install_openclaw_orchestrator_skill.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SKILL_NAME = "mission-control-orchestrator"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Install the Mission Control OpenClaw orchestrator skill."
    )
    parser.add_argument(
        "--install-dir",
        default=os.environ.get(
            "OPENCLAW_SKILLS_DIR", str(Path.home() / ".openclaw" / "skills")
        ),
        help="Directory where the skill will be installed.",
    )
    parser.add_argument(
        "--state-dir",
        default=os.environ.get(
            "OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw" / "state")
        ),
        help="OpenClaw state directory containing latest_run.json.",
    )
    parser.add_argument(
        "--sqlite-path",
        default=os.environ.get(
            "OPENCLAW_SQLITE_PATH",
            str(Path.home() / ".openclaw" / "state" / "orchestrator.sqlite"),
        ),
        help="Sqlite checkpoint file used by LangGraph SqliteSaver.",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Skip dependency installation from requirements.txt.",
    )
    return parser.parse_args()


def _repo_root() -> Path:
    """Resolve repository root from script location."""

    return Path(__file__).resolve().parent.parent


def install_dependencies(repo_root: Path) -> None:
    """Install project dependencies via pip."""

    requirements = repo_root / "requirements.txt"
    if not requirements.exists():
        raise FileNotFoundError(f"requirements.txt not found at {requirements}")

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
        check=True,
    )


def build_manifest_payload(state_dir: str, sqlite_path: str) -> dict[str, Any]:
    """Build a skill manifest payload consumable by OpenClaw/ClawHub runtimes."""

    return {
        "name": SKILL_NAME,
        "description": "LangGraph Supervisor-Worker orchestrator for Mission Control.",
        "entrypoint": "openclaw_orchestrator.graph:build_app",
        "models": {
            "supervisor": "gemini-flash",
            "developer": "claude-3.5-sonnet",
            "qa": "claude-3.5-haiku",
        },
        "env": {
            "OPENCLAW_STATE_DIR": state_dir,
            "OPENCLAW_SQLITE_PATH": sqlite_path,
        },
    }


def install_skill_package(repo_root: Path, install_dir: Path) -> Path:
    """Copy package files into install directory and return installed path."""

    source_dir = repo_root / "openclaw_orchestrator"
    if not source_dir.exists():
        raise FileNotFoundError(f"Package directory not found: {source_dir}")

    target_root = install_dir / SKILL_NAME
    target_package = target_root / "openclaw_orchestrator"
    target_root.mkdir(parents=True, exist_ok=True)

    if target_package.exists():
        shutil.rmtree(target_package)
    shutil.copytree(source_dir, target_package)

    return target_root


def write_runtime_files(skill_root: Path, state_dir: str, sqlite_path: str) -> None:
    """Write manifest and environment files for runtime bootstrapping."""

    manifest = build_manifest_payload(state_dir=state_dir, sqlite_path=sqlite_path)

    manifest_path = skill_root / "skill_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    env_path = skill_root / ".env"
    env_path.write_text(
        "\n".join(
            [
                f"OPENCLAW_STATE_DIR={state_dir}",
                f"OPENCLAW_SQLITE_PATH={sqlite_path}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def smoke_test(skill_root: Path) -> None:
    """Validate that the installed package can be imported."""

    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{skill_root}{os.pathsep}{pythonpath}" if pythonpath else str(skill_root)
    )

    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from openclaw_orchestrator import build_skill_definition; "
                "print(build_skill_definition().name)"
            ),
        ],
        check=True,
        env=env,
    )


def main() -> int:
    """Run the installer workflow."""

    args = parse_args()
    repo_root = _repo_root()
    install_dir = Path(args.install_dir).expanduser().resolve()

    if not args.skip_deps:
        install_dependencies(repo_root)

    skill_root = install_skill_package(repo_root=repo_root, install_dir=install_dir)
    write_runtime_files(
        skill_root=skill_root,
        state_dir=str(Path(args.state_dir).expanduser()),
        sqlite_path=str(Path(args.sqlite_path).expanduser()),
    )
    smoke_test(skill_root)

    print("✅ Skill instalada correctamente")
    print(f"📁 Directorio: {skill_root}")
    print(f"🧾 Manifest: {skill_root / 'skill_manifest.json'}")
    print("Siguiente paso: registra 'skill_manifest.json' en tu runtime OpenClaw/ClawHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
