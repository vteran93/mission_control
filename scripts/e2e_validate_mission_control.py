#!/usr/bin/env python3
"""End-to-end validator for Mission Control + OpenClaw orchestrator.

This script behaves like a unit-style E2E test harness:
1. Initializes Mission Control database.
2. Starts Mission Control API server.
3. Validates a simple workflow using 3 agents (PM, Dev, QA).
4. Validates OpenClaw orchestrator imports and LangGraph wiring.

By default the script is strict: missing LangGraph fails the run.
Use ``--allow-missing-langgraph`` to continue in constrained environments.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = "http://127.0.0.1:5001"


def parse_args() -> argparse.Namespace:
    """Parse CLI flags."""

    parser = argparse.ArgumentParser(
        description="Run a full Mission Control + orchestrator E2E validation."
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to the mission_control repository root.",
    )
    parser.add_argument(
        "--allow-missing-langgraph",
        action="store_true",
        help="Continue if LangGraph is unavailable in the current environment.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=30,
        help="Seconds to wait for Mission Control API startup.",
    )
    return parser.parse_args()


def run_cmd(cmd: list[str], cwd: Path) -> None:
    """Run shell command and fail fast on non-zero exit code."""

    subprocess.run(cmd, cwd=str(cwd), check=True)


def api_call(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    """Call JSON API endpoint and return status + parsed body."""

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def wait_for_api(timeout_s: int) -> None:
    """Poll API health endpoint until ready or timeout."""

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            status, _ = api_call("GET", "/api/agents")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("Mission Control API did not become ready in time.")


def ensure_agent(name: str, role: str) -> dict[str, Any]:
    """Ensure agent exists, creating it if necessary."""

    status, agents = api_call("GET", "/api/agents")
    if status != 200:
        raise RuntimeError(f"Cannot list agents: status={status}, body={agents}")

    for agent in agents:
        if agent.get("name") == name:
            return agent

    status, created = api_call("POST", "/api/agents", {"name": name, "role": role})
    if status != 201:
        raise RuntimeError(f"Cannot create {name}: status={status}, body={created}")
    return created


def validate_three_agent_flow() -> dict[str, Any]:
    """Validate simple end-to-end task flow with PM/Dev/QA agents."""

    pm = ensure_agent("Jarvis-PM", "pm")
    dev = ensure_agent("Jarvis-Dev", "dev")
    qa = ensure_agent("Jarvis-QA", "qa")

    for agent in (pm, dev, qa):
        status, _ = api_call("PUT", f"/api/agents/{agent['id']}", {"status": "working"})
        if status != 200:
            raise RuntimeError(f"Cannot update status for {agent['name']}: {status}")

    status, task = api_call(
        "POST",
        "/api/tasks",
        {
            "title": "TICKET-E2E-THREE-AGENTS",
            "description": "E2E simple task routed PM -> Dev -> QA",
            "priority": "high",
            "status": "in_progress",
            "assignee_agent_ids": f"{pm['id']},{dev['id']},{qa['id']}",
            "created_by": "E2E-Script",
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot create task: {status}, {task}")

    task_id = task["id"]

    message_payloads = [
        {
            "task_id": task_id,
            "from_agent": "Jarvis-PM",
            "content": "@Jarvis-Dev implementa una solución mínima.",
        },
        {
            "task_id": task_id,
            "from_agent": "Jarvis-Dev",
            "content": "@Jarvis-QA listo para validación.",
        },
        {
            "task_id": task_id,
            "from_agent": "Jarvis-QA",
            "content": "@Jarvis-PM aprobado para cierre.",
        },
    ]

    message_ids: list[int] = []
    for payload in message_payloads:
        status, msg = api_call("POST", "/api/messages", payload)
        if status != 201:
            raise RuntimeError(f"Cannot create message: {status}, {msg}")
        message_ids.append(msg["id"])

    status, document = api_call(
        "POST",
        "/api/documents",
        {
            "title": "e2e_validation_report.md",
            "content_md": "# E2E\nFlujo PM/Dev/QA completado.",
            "type": "note",
            "task_id": task_id,
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot create document: {status}, {document}")

    status, notification = api_call(
        "POST",
        "/api/notifications",
        {
            "agent_id": pm["id"],
            "content": f"Task {task_id} aprobada por QA",
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot create notification: {status}, {notification}")

    status, queued = api_call(
        "POST",
        "/api/send-agent-message",
        {
            "target_agent": "jarvis-dev",
            "message": f"E2E queued follow-up for task {task_id}",
            "task_id": task_id,
        },
    )
    if status != 200 or queued.get("status") != "queued":
        raise RuntimeError(f"Cannot queue agent message: {status}, {queued}")

    status, task_after = api_call("PUT", f"/api/tasks/{task_id}", {"status": "done"})
    if status != 200:
        raise RuntimeError(f"Cannot close task: {status}, {task_after}")

    status, messages = api_call("GET", f"/api/messages?task_id={task_id}")
    if status != 200 or len(messages) < 3:
        raise RuntimeError(f"Unexpected task messages: {status}, {messages}")

    return {
        "task_id": task_id,
        "message_ids": message_ids,
        "document_id": document["id"],
        "notification_id": notification["id"],
        "queued_message_id": queued.get("message_id"),
    }


def validate_langgraph_wiring(allow_missing: bool) -> dict[str, Any]:
    """Validate orchestrator package and LangGraph integration."""

    from openclaw_orchestrator import OpenClawBridge, build_skill_definition

    skill = build_skill_definition()
    result: dict[str, Any] = {
        "skill_name": skill.name,
        "entrypoint": skill.entrypoint,
        "langgraph_validated": False,
    }

    with tempfile.TemporaryDirectory(prefix="e2e-openclaw-") as tmp:
        state_dir = Path(tmp) / ".openclaw" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        latest = state_dir / "latest_run.json"
        latest.write_text(
            json.dumps(
                {
                    "last_terminal_output": "pytest passed",
                    "filesystem_diffs": "diff --git a/main.py b/main.py",
                }
            ),
            encoding="utf-8",
        )

        bridge = OpenClawBridge(state_dir=str(state_dir))
        snapshot = bridge.snapshot()
        result["snapshot_checkpoint"] = snapshot.disk_checkpoint

        try:
            import langgraph  # noqa: F401
            from openclaw_orchestrator.graph import build_graph

            graph = build_graph(bridge)
            if graph is None:
                raise RuntimeError("build_graph returned None")
            result["langgraph_validated"] = True
        except Exception as exc:
            if allow_missing:
                result["langgraph_warning"] = str(exc)
            else:
                raise RuntimeError(f"LangGraph validation failed: {exc}") from exc

    return result


def main() -> int:
    """Execute end-to-end validation workflow."""

    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    run_cmd([sys.executable, "init_db.py"], cwd=repo_root)

    server = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_api(args.startup_timeout)
        api_result = validate_three_agent_flow()
        langgraph_result = validate_langgraph_wiring(args.allow_missing_langgraph)

        print(
            json.dumps(
                {
                    "mission_control_e2e": "ok",
                    "three_agent_flow": api_result,
                    "orchestrator_validation": langgraph_result,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        if server.poll() is None:
            server.send_signal(signal.SIGINT)
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
