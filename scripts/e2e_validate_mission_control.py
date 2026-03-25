#!/usr/bin/env python3
"""End-to-end validator for Mission Control.

This script validates three layers over a real HTTP server:
1. Core PM/Dev/QA workflow.
2. Phase 4 autonomous scrum workflow with mandatory CrewAI planning.
3. OpenClaw orchestrator imports and LangGraph wiring.

The Phase 4 path is deterministic: the script injects a temporary fake
``crewai`` package through ``PYTHONPATH`` so the runtime can execute
planning/review flows without external providers.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def maybe_reexec_in_repo_venv(repo_root: Path) -> None:
    """Prefer the repository virtualenv to avoid leaking global Python state."""

    sentinel = "MISSION_CONTROL_E2E_VENV_REEXEC"
    venv_python = repo_root / ".venv" / "bin" / "python"
    if os.environ.get(sentinel) == "1":
        return
    if not venv_python.is_file():
        return

    current_prefix = Path(sys.prefix).resolve()
    target_prefix = (repo_root / ".venv").resolve()
    if current_prefix == target_prefix:
        return

    env = os.environ.copy()
    env[sentinel] = "1"
    os.execve(
        str(venv_python),
        [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        env,
    )


def resolve_repo_python(repo_root: Path) -> str:
    """Return the preferred interpreter for subprocesses spawned by the E2E harness."""

    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def parse_args() -> argparse.Namespace:
    """Parse CLI flags."""

    parser = argparse.ArgumentParser(
        description="Run a full Mission Control end-to-end validation."
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to the mission_control repository root.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port for the temporary Mission Control server.",
    )
    parser.add_argument(
        "--project-root",
        help="External project root containing requirements.md and roadmap.md for the Phase 4 E2E path.",
    )
    parser.add_argument(
        "--requirements-path",
        help="Explicit requirements.md path for the Phase 4 E2E path.",
    )
    parser.add_argument(
        "--roadmap-path",
        help="Explicit roadmap.md path for the Phase 4 E2E path.",
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


def run_cmd(cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> None:
    """Run shell command and fail fast on non-zero exit code."""

    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def api_call(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Call JSON API endpoint and return status + parsed body."""

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url + path, data=data, method=method)
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


def wait_for_api(base_url: str, timeout_s: int) -> None:
    """Poll API health endpoint until ready or timeout."""

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            status, _ = api_call(base_url, "GET", "/api/health")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("Mission Control API did not become ready in time.")


def ensure_agent(base_url: str, name: str, role: str) -> dict[str, Any]:
    """Ensure agent exists, creating it if necessary."""

    status, agents = api_call(base_url, "GET", "/api/agents")
    if status != 200:
        raise RuntimeError(f"Cannot list agents: status={status}, body={agents}")

    for agent in agents:
        if agent.get("name") == name:
            return agent

    status, created = api_call(base_url, "POST", "/api/agents", {"name": name, "role": role})
    if status != 201:
        raise RuntimeError(f"Cannot create {name}: status={status}, body={created}")
    return created


def validate_three_agent_flow(base_url: str) -> dict[str, Any]:
    """Validate simple end-to-end task flow with PM/Dev/QA agents."""

    pm = ensure_agent(base_url, "Jarvis-PM", "pm")
    dev = ensure_agent(base_url, "Jarvis-Dev", "dev")
    qa = ensure_agent(base_url, "Jarvis-QA", "qa")

    for agent in (pm, dev, qa):
        status, _ = api_call(base_url, "PUT", f"/api/agents/{agent['id']}", {"status": "working"})
        if status != 200:
            raise RuntimeError(f"Cannot update status for {agent['name']}: {status}")

    status, task = api_call(
        base_url,
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
        status, msg = api_call(base_url, "POST", "/api/messages", payload)
        if status != 201:
            raise RuntimeError(f"Cannot create message: {status}, {msg}")
        message_ids.append(msg["id"])

    status, document = api_call(
        base_url,
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
        base_url,
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
        base_url,
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

    status, task_after = api_call(base_url, "PUT", f"/api/tasks/{task_id}", {"status": "done"})
    if status != 200:
        raise RuntimeError(f"Cannot close task: {status}, {task_after}")

    status, messages = api_call(base_url, "GET", f"/api/messages?task_id={task_id}")
    if status != 200 or len(messages) < 3:
        raise RuntimeError(f"Unexpected task messages: {status}, {messages}")

    return {
        "task_id": task_id,
        "message_ids": message_ids,
        "document_id": document["id"],
        "notification_id": notification["id"],
        "queued_message_id": queued.get("message_id"),
    }


def create_fake_crewai_package(root_dir: Path, responses_path: Path) -> Path:
    """Create a minimal CrewAI-compatible package for deterministic E2E runs."""

    package_dir = root_dir / "crewai"
    package_dir.mkdir(parents=True, exist_ok=True)
    package_dir.joinpath("__init__.py").write_text(
        textwrap.dedent(
            f"""
            import json
            import os
            from pathlib import Path


            RESPONSES_PATH = Path({str(responses_path)!r})


            class LLM:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs


            class Agent:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs


            class Task:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs


            class Process:
                hierarchical = "hierarchical"


            class Crew:
                last_kwargs = None

                def __init__(self, **kwargs):
                    Crew.last_kwargs = kwargs
                    self.kwargs = kwargs

                def kickoff(self):
                    if RESPONSES_PATH.is_file():
                        payload = json.loads(RESPONSES_PATH.read_text(encoding="utf-8"))
                    else:
                        payload = []
                    next_item = payload.pop(0) if payload else None
                    RESPONSES_PATH.write_text(json.dumps(payload), encoding="utf-8")

                    if isinstance(next_item, dict) and next_item.get("error"):
                        raise RuntimeError(next_item["error"])
                    if isinstance(next_item, dict):
                        raw = next_item.get("raw")
                    else:
                        raw = next_item
                    if raw is None:
                        raw = '{{"approval_status":"approved","summary":"fake crew default","risks":[],"actions":["continue"]}}'

                    return type("CrewOutput", (), {{"raw": str(raw)}})()
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return root_dir


def set_fake_crewai_outputs(responses_path: Path, outputs: list[dict[str, str] | str]) -> None:
    responses_path.write_text(json.dumps(outputs), encoding="utf-8")


def approved_review(summary: str) -> str:
    return json.dumps(
        {
            "approval_status": "approved",
            "summary": summary,
            "risks": [],
            "actions": ["ejecutar"],
        },
        ensure_ascii=False,
    )


def review_required_review(summary: str) -> str:
    return json.dumps(
        {
            "approval_status": "review_required",
            "summary": summary,
            "risks": ["baja confianza del plan"],
            "actions": ["revisar y aprobar"],
        },
        ensure_ascii=False,
    )


def resolve_external_phase4_specs(args: argparse.Namespace) -> tuple[Path, Path, str] | None:
    """Resolve external specs for a real-project Phase 4 E2E run."""

    if args.requirements_path or args.roadmap_path:
        if not args.requirements_path or not args.roadmap_path:
            raise RuntimeError("Both --requirements-path and --roadmap-path are required together")
        requirements_path = Path(args.requirements_path).expanduser().resolve()
        roadmap_path = Path(args.roadmap_path).expanduser().resolve()
        if not requirements_path.is_file():
            raise RuntimeError(f"requirements path not found: {requirements_path}")
        if not roadmap_path.is_file():
            raise RuntimeError(f"roadmap path not found: {roadmap_path}")
        return requirements_path, roadmap_path, requirements_path.parent.name

    if args.project_root:
        project_root = Path(args.project_root).expanduser().resolve()
        requirements_path = project_root / "requirements.md"
        roadmap_path = project_root / "roadmap.md"
        if not requirements_path.is_file():
            raise RuntimeError(f"requirements.md not found in project root: {requirements_path}")
        if not roadmap_path.is_file():
            raise RuntimeError(f"roadmap.md not found in project root: {roadmap_path}")
        return requirements_path, roadmap_path, project_root.name

    return None


def write_phase4_specs(fixtures_dir: Path) -> dict[str, tuple[Path, Path]]:
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    approved_requirements = fixtures_dir / "approved_requirements.md"
    approved_roadmap = fixtures_dir / "approved_roadmap.md"
    approved_requirements.write_text(
        textwrap.dedent(
            """
            # Mission Control Phase 4 Approved
            ## Objetivo
            - Debe planificar sprints automaticamente
            - Debe aprobar backlog listo para ejecucion
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    approved_roadmap.write_text(
        textwrap.dedent(
            """
            # Roadmap
            **Proyecto**: Mission Control Phase 4 Approved

            ## EP-4 · Scrum Planning
            > Objetivo: generar sprints listos para ejecucion.

            ### TICKET-401 · Normalizar backlog inicial
            ```
            Tipo: feature
            Prioridad: P0
            Est.: 4 h
            Deps.: ninguna
            ```

            **Descripción**
            Construir backlog inicial derivado del blueprint.

            **Criterios de aceptación**
            - [ ] Genera tareas normalizadas
            - [ ] Preserva dependencias

            ### TICKET-402 · Planificar capacidad por sprint
            ```
            Tipo: feature
            Prioridad: P1
            Est.: 8 h
            Deps.: TICKET-401
            ```

            **Descripción**
            Distribuir tickets por sprint segun capacidad efectiva.

            **Criterios de aceptación**
            - [ ] Agrupa tickets por sprint
            - [ ] Respeta dependencias
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    review_requirements = fixtures_dir / "review_requirements.md"
    review_roadmap = fixtures_dir / "review_roadmap.md"
    review_requirements.write_text(
        textwrap.dedent(
            """
            # Mission Control Phase 4 Review Required
            ## Objetivo
            - Debe detectar planes con baja confianza
            - Debe requerir aprobacion antes de ejecutar autonomamente
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    review_roadmap.write_text(
        textwrap.dedent(
            """
            # Roadmap
            **Proyecto**: Mission Control Phase 4 Review Required

            ## EP-4 · Scrum Planning
            > Objetivo: generar sprints desde un backlog incompleto.

            ### TICKET-501 · Descubrir alcance real
            ```
            Tipo: spike
            Prioridad: P0
            Deps.: ninguna
            ```

            ### TICKET-502 · Preparar plan operativo
            ```
            Tipo: feature
            Prioridad: P1
            Deps.: TICKET-501
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    return {
        "approved": (approved_requirements, approved_roadmap),
        "review_required": (review_requirements, review_roadmap),
    }


def import_blueprint(base_url: str, requirements_path: Path, roadmap_path: Path) -> dict[str, Any]:
    status, payload = api_call(
        base_url,
        "POST",
        "/api/blueprints/import",
        {
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot import blueprint: status={status}, body={payload}")
    return payload


def validate_phase4_scrum_workflow(
    base_url: str,
    fixtures_dir: Path,
    responses_path: Path,
) -> dict[str, Any]:
    """Validate the autonomous scrum planner over the public HTTP API."""

    status, runtime_health = api_call(base_url, "GET", "/api/runtime/health")
    if status != 200:
        raise RuntimeError(f"Cannot read runtime health: status={status}, body={runtime_health}")
    if runtime_health["runtime"]["dispatch_ready"] is not True:
        raise RuntimeError(f"Runtime is not dispatch-ready for Phase 4 validation: {runtime_health}")
    if "scrum_planning" not in runtime_health["toolkit"]["crew_seeds"]:
        raise RuntimeError(f"'scrum_planning' seed missing from runtime health: {runtime_health}")

    specs = write_phase4_specs(fixtures_dir)

    set_fake_crewai_outputs(responses_path, [approved_review("Planning crew aprueba el plan.")])
    approved_blueprint = import_blueprint(base_url, *specs["approved"])
    approved_blueprint_id = approved_blueprint["id"]

    status, approved_plan = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{approved_blueprint_id}/scrum-plan",
        {
            "sprint_capacity": 5,
            "sprint_length_days": 7,
            "start_date": "2026-03-24T09:00:00",
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot create approved scrum plan: status={status}, body={approved_plan}")
    if approved_plan["approval_status"] != "approved" or approved_plan["status"] != "active":
        raise RuntimeError(f"Approved plan did not reach active state: {approved_plan}")
    if approved_plan["summary"]["planning_crew"]["metadata"]["provider"] != "bedrock":
        raise RuntimeError(f"Planning crew did not route through Bedrock profile: {approved_plan}")

    status, approved_sprint_view = api_call(
        base_url,
        "GET",
        f"/api/blueprints/{approved_blueprint_id}/scrum-plan/sprint-view",
    )
    if status != 200:
        raise RuntimeError(f"Cannot read approved sprint view: status={status}, body={approved_sprint_view}")
    if approved_sprint_view["plan"]["execution_ready"] is not True:
        raise RuntimeError(f"Approved sprint view is not execution-ready: {approved_sprint_view}")

    set_fake_crewai_outputs(
        responses_path,
        [
            review_required_review("Planning crew requiere revision adicional."),
            review_required_review("Reviewer senior mantiene el plan en review."),
        ],
    )
    review_blueprint = import_blueprint(base_url, *specs["review_required"])
    review_blueprint_id = review_blueprint["id"]

    status, review_plan = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{review_blueprint_id}/scrum-plan",
        {"sprint_capacity": 5},
    )
    if status != 201:
        raise RuntimeError(f"Cannot create review-required scrum plan: status={status}, body={review_plan}")
    if review_plan["escalation_trigger"] != "bedrock_review":
        raise RuntimeError(f"Expected bedrock_review escalation trigger: {review_plan}")
    if review_plan["approval_status"] != "review_required" or review_plan["status"] != "draft":
        raise RuntimeError(f"Review-required plan has invalid lifecycle state: {review_plan}")
    if review_plan["summary"]["senior_review"]["metadata"]["provider"] != "bedrock":
        raise RuntimeError(f"Senior review did not run on Bedrock: {review_plan}")

    status, latest_review_plan = api_call(
        base_url,
        "GET",
        f"/api/blueprints/{review_blueprint_id}/scrum-plan?status=latest",
    )
    if status != 200 or latest_review_plan["id"] != review_plan["id"]:
        raise RuntimeError(f"Latest plan lookup failed for draft plan: {latest_review_plan}")

    status, review_sprint_view = api_call(
        base_url,
        "GET",
        f"/api/blueprints/{review_blueprint_id}/scrum-plan/sprint-view?status=latest",
    )
    if status != 200:
        raise RuntimeError(f"Cannot read review-required sprint view: status={status}, body={review_sprint_view}")
    if review_sprint_view["summary"]["overall_readiness"] != "review_required":
        raise RuntimeError(f"Sprint view should reflect review_required readiness: {review_sprint_view}")

    status, approved_after_manual = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{review_blueprint_id}/scrum-plan/{review_plan['id']}/approve",
        {
            "source": "e2e_script",
            "feedback_text": "Aprobado manualmente en flujo E2E.",
        },
    )
    if status != 200:
        raise RuntimeError(f"Cannot manually approve draft scrum plan: status={status}, body={approved_after_manual}")
    if approved_after_manual["approval_status"] != "approved" or approved_after_manual["status"] != "active":
        raise RuntimeError(f"Manual approval did not promote the plan: {approved_after_manual}")

    status, review_report = api_call(base_url, "GET", f"/api/blueprints/{review_blueprint_id}/report")
    if status != 200:
        raise RuntimeError(f"Cannot read review blueprint report: status={status}, body={review_report}")

    return {
        "approved_blueprint_id": approved_blueprint_id,
        "approved_plan_id": approved_plan["id"],
        "approved_plan_version": approved_plan["version"],
        "approved_sprints": approved_sprint_view["summary"]["sprint_count"],
        "review_blueprint_id": review_blueprint_id,
        "review_plan_id": review_plan["id"],
        "review_plan_version": review_plan["version"],
        "review_escalation_trigger": review_plan["escalation_trigger"],
        "review_readiness": review_sprint_view["summary"]["overall_readiness"],
        "manual_approval_status": approved_after_manual["approval_status"],
        "manual_approval_report_counts": review_report["counts"],
    }


def validate_phase4_real_project_workflow(
    base_url: str,
    responses_path: Path,
    *,
    requirements_path: Path,
    roadmap_path: Path,
    project_label: str,
) -> dict[str, Any]:
    """Validate the autonomous scrum planner against a real external project."""

    status, runtime_health = api_call(base_url, "GET", "/api/runtime/health")
    if status != 200:
        raise RuntimeError(f"Cannot read runtime health: status={status}, body={runtime_health}")
    if runtime_health["runtime"]["dispatch_ready"] is not True:
        raise RuntimeError(f"Runtime is not dispatch-ready for Phase 4 validation: {runtime_health}")
    if "scrum_planning" not in runtime_health["toolkit"]["crew_seeds"]:
        raise RuntimeError(f"'scrum_planning' seed missing from runtime health: {runtime_health}")

    set_fake_crewai_outputs(
        responses_path,
        [
            approved_review(f"Planning crew aprueba el plan para {project_label}."),
            approved_review(f"Planning crew aprueba el replan para {project_label}."),
        ],
    )
    blueprint = import_blueprint(base_url, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    status, plan = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        {
            "sprint_capacity": 16,
            "sprint_length_days": 7,
            "start_date": "2026-03-24T09:00:00",
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot create scrum plan for {project_label}: status={status}, body={plan}")
    if plan["approval_status"] != "approved" or plan["status"] != "active":
        raise RuntimeError(f"Real-project plan did not reach active/approved state: {plan}")
    if plan["summary"]["planning_crew"]["metadata"]["provider"] != "bedrock":
        raise RuntimeError(f"Planning crew did not route through Bedrock profile: {plan}")

    status, sprint_view = api_call(
        base_url,
        "GET",
        f"/api/blueprints/{blueprint_id}/scrum-plan/sprint-view",
    )
    if status != 200:
        raise RuntimeError(f"Cannot read sprint view for {project_label}: status={status}, body={sprint_view}")
    if sprint_view["plan"]["execution_ready"] is not True:
        raise RuntimeError(f"Real-project sprint view is not execution-ready: {sprint_view}")

    if not plan["items"]:
        raise RuntimeError(f"Real-project plan has no items: {plan}")
    blocked_ticket_id = plan["items"][0]["ticket_id"]

    status, replan = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/scrum-plan/replan",
        {
            "sprint_capacity": 16,
            "blocked_ticket_ids": [blocked_ticket_id],
            "reason": f"E2E replan validation for {project_label}",
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot replan scrum flow for {project_label}: status={status}, body={replan}")
    if replan["version"] <= plan["version"]:
        raise RuntimeError(f"Replan did not create a new version: {replan}")

    status, plans = api_call(base_url, "GET", f"/api/blueprints/{blueprint_id}/scrum-plans")
    if status != 200:
        raise RuntimeError(f"Cannot list scrum plans for {project_label}: status={status}, body={plans}")
    if len(plans) < 2:
        raise RuntimeError(f"Expected at least 2 scrum plans after replan: {plans}")

    status, report = api_call(base_url, "GET", f"/api/blueprints/{blueprint_id}/report")
    if status != 200:
        raise RuntimeError(f"Cannot read report for {project_label}: status={status}, body={report}")

    return {
        "project_label": project_label,
        "requirements_path": str(requirements_path),
        "roadmap_path": str(roadmap_path),
        "blueprint_id": blueprint_id,
        "requirements_count": blueprint["summary"]["requirements_count"],
        "tickets_count": blueprint["summary"]["tickets_count"],
        "initial_plan_id": plan["id"],
        "initial_plan_version": plan["version"],
        "initial_sprints_planned": plan["summary"]["sprints_planned"],
        "replan_id": replan["id"],
        "replan_version": replan["version"],
        "blocked_ticket_id": blocked_ticket_id,
        "latest_sprint_count": sprint_view["summary"]["sprint_count"],
        "latest_total_consumed_capacity": sprint_view["summary"]["total_consumed_capacity"],
        "report_counts": report["counts"],
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


def prepare_e2e_env(
    repo_root: Path,
    temp_root: Path,
    *,
    port: int,
    fake_crewai_root: Path,
    responses_path: Path,
) -> dict[str, str]:
    """Build an isolated environment for init_db + app subprocesses."""

    instance_path = temp_root / "instance"
    runtime_dir = temp_root / "runtime"
    queue_dir = runtime_dir / "queue"
    lock_dir = runtime_dir / "locks"
    scripts_dir = repo_root / "scripts"
    database_path = instance_path / "mission_control_e2e.db"

    instance_path.mkdir(parents=True, exist_ok=True)
    queue_dir.mkdir(parents=True, exist_ok=True)
    lock_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "FLASK_DEBUG": "false",
            "PORT": str(port),
            "DATABASE_URL": f"sqlite:///{database_path}",
            "MISSION_CONTROL_INSTANCE_PATH": str(instance_path),
            "MISSION_CONTROL_RUNTIME_DIR": str(runtime_dir),
            "MISSION_CONTROL_QUEUE_DIR": str(queue_dir),
            "MISSION_CONTROL_HEARTBEAT_LOCK_DIR": str(lock_dir),
            "MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR": str(scripts_dir),
            "MISSION_CONTROL_DISPATCHER_EXECUTOR": "crewai",
            "MISSION_CONTROL_DISPATCHER_AUTOSTART": "false",
            "MISSION_CONTROL_DISPATCHER_ENABLE_FALLBACK": "true",
            "MISSION_CONTROL_DISPATCHER_ESCALATE_AFTER_RETRIES": "1",
            "MISSION_CONTROL_LLM_TIMEOUT_SECONDS": "45",
            "MISSION_CONTROL_LLM_MAX_TOKENS": "2048",
            "OLLAMA_DEFAULT_MODEL": "qwen2.5-coder:latest",
            "OLLAMA_BASE_URL": "http://ollama:11434",
            "BEDROCK_REGION": "us-east-1",
            "BEDROCK_PLANNER_MODEL": "anthropic.claude-3-7-sonnet",
            "BEDROCK_REVIEWER_MODEL": "anthropic.claude-3-5-sonnet",
            "FAKE_CREWAI_RESPONSES_PATH": str(responses_path),
        }
    )
    existing_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_entries = [str(fake_crewai_root), str(repo_root)]
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return env


def resolve_port(port: int) -> int:
    """Return the requested port when available or a free fallback port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", port)) != 0:
            return port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    """Execute end-to-end validation workflow."""

    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    maybe_reexec_in_repo_venv(repo_root)
    python_bin = resolve_repo_python(repo_root)
    resolved_port = resolve_port(args.port)
    base_url = f"http://127.0.0.1:{resolved_port}"
    external_phase4_specs = resolve_external_phase4_specs(args)

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    with tempfile.TemporaryDirectory(prefix="mission-control-e2e-") as tmp:
        temp_root = Path(tmp)
        fake_crewai_root = temp_root / "fake_site"
        responses_path = temp_root / "fake_crewai_responses.json"
        fixtures_dir = temp_root / "fixtures"
        create_fake_crewai_package(fake_crewai_root, responses_path)
        env = prepare_e2e_env(
            repo_root,
            temp_root,
            port=resolved_port,
            fake_crewai_root=fake_crewai_root,
            responses_path=responses_path,
        )

        run_cmd([python_bin, "init_db.py"], cwd=repo_root, env=env)

        server = subprocess.Popen(
            [python_bin, "app.py"],
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            wait_for_api(base_url, args.startup_timeout)
            api_result = validate_three_agent_flow(base_url)
            if external_phase4_specs is not None:
                requirements_path, roadmap_path, project_label = external_phase4_specs
                phase4_result = validate_phase4_real_project_workflow(
                    base_url,
                    responses_path,
                    requirements_path=requirements_path,
                    roadmap_path=roadmap_path,
                    project_label=project_label,
                )
            else:
                phase4_result = validate_phase4_scrum_workflow(base_url, fixtures_dir, responses_path)
            langgraph_result = validate_langgraph_wiring(args.allow_missing_langgraph)

            print(
                json.dumps(
                    {
                        "mission_control_e2e": "ok",
                        "base_url": base_url,
                        "three_agent_flow": api_result,
                        "phase4_scrum_flow": phase4_result,
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
