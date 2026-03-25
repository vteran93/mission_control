#!/usr/bin/env python3
"""End-to-end validator for Mission Control.

This script validates three layers over a real HTTP server:
1. Core PM/Dev/QA workflow.
2. Phase 4 autonomous scrum workflow with mandatory CrewAI planning.
3. Phase 5 semi-automatic delivery workflow that writes real files to disk.
4. OpenClaw orchestrator imports and LangGraph wiring.

The Phase 4 path is deterministic: the script injects a temporary fake
``crewai`` package through ``PYTHONPATH`` so the runtime can execute
planning/review flows without external providers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def write_phase5_specs(fixtures_dir: Path) -> tuple[Path, Path]:
    phase5_requirements = fixtures_dir / "phase5_requirements.md"
    phase5_roadmap = fixtures_dir / "phase5_roadmap.md"

    phase5_requirements.write_text(
        textwrap.dedent(
            """
            # Mission Control Phase 5
            ## Objetivo
            - Debe ejecutar un modo semiautomatico para artefactos simples
            - Debe escribir archivos reales en disco dentro del workspace objetivo
            - Debe dejar evidencia de ejecucion en Postgres
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    phase5_roadmap.write_text(
        textwrap.dedent(
            """
            # Roadmap
            **Proyecto**: Mission Control Phase 5

            ## EP-5 · Autonomous Delivery Loop
            > Objetivo: materializar artefactos simples en modo semiautomatico.

            ### TICKET-501 · Escribir examples/holamundo.py
            ```
            Tipo: feature
            Prioridad: P0
            Est.: 1 h
            Deps.: ninguna
            ```

            **Descripción**
            Crear un archivo Python en examples/holamundo.py que imprima Hola Mundo.

            **Criterios de aceptación**
            - [ ] Existe examples/holamundo.py
            - [ ] El script imprime Hola Mundo al ejecutarse

            ### TICKET-502 · Escribir pagina React Hola Mundo en frontend
            ```
            Tipo: feature
            Prioridad: P1
            Est.: 2 h
            Deps.: ninguna
            ```

            **Descripción**
            Crear una pagina web con React JS Hola Mundo en una carpeta frontend.

            **Criterios de aceptación**
            - [ ] Existe frontend/index.html
            - [ ] La pagina monta un root de React
            - [ ] La pagina muestra Hola Mundo

            ### TICKET-503 · Escribir modulo Terraform S3 en infra
            ```
            Tipo: feature
            Prioridad: P1
            Est.: 2 h
            Deps.: ninguna
            ```

            **Descripción**
            Crear un modulo de Terraform con un recurso S3 basico en una carpeta infra.

            **Criterios de aceptación**
            - [ ] Existe infra/main.tf
            - [ ] El modulo declara aws_s3_bucket.basic
            - [ ] El bucket usa una variable bucket_name
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    return phase5_requirements, phase5_roadmap


def write_phase6_specs(fixtures_dir: Path) -> tuple[Path, Path]:
    phase6_requirements = fixtures_dir / "phase6_requirements.md"
    phase6_roadmap = fixtures_dir / "phase6_roadmap.md"

    phase6_requirements.write_text(
        textwrap.dedent(
            """
            # Mission Control Phase 6
            ## Objetivo
            - Debe sincronizar governance de GitHub con GitHub App
            - Debe exponer observabilidad profunda por blueprint y PR
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    phase6_roadmap.write_text(
        textwrap.dedent(
            """
            # Roadmap
            **Proyecto**: Mission Control Phase 6

            ## EP-6 · Operator GitHub Control
            > Objetivo: sincronizar PRs y branch protection desde el panel operador.

            ### TICKET-601 · Sincronizar branch protection
            ```
            Tipo: feature
            Prioridad: P0
            Est.: 2 h
            Deps.: ninguna
            ```

            **Descripción**
            Sincronizar branches protegidas con GitHub App.

            **Criterios de aceptación**
            - [ ] Se sincroniza protection de main y release

            ### TICKET-602 · Exponer dashboard profundo por blueprint
            ```
            Tipo: feature
            Prioridad: P1
            Est.: 2 h
            Deps.: TICKET-601
            ```

            **Descripción**
            Mostrar PRs, runs, feedback y retrospective asociados al blueprint.

            **Criterios de aceptación**
            - [ ] El dashboard muestra PRs del blueprint
            - [ ] El dashboard muestra feedback y retrospective
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    return phase6_requirements, phase6_roadmap


def generate_github_app_private_key_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


class FakeGitHubServer:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "blueprint_id": None,
            "installation_token_requests": [],
            "branch_protection_requests": [],
            "pull_request_fetches": [],
        }
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._build_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def api_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/api/v3"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def _build_handler(self):
        server_state = self.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def _read_json(self) -> dict[str, Any]:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0:
                    return {}
                raw = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw) if raw else {}

            def _send_json(self, status_code: int, payload: Any) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_POST(self) -> None:  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/api/v3/app/installations/98765/access_tokens":
                    server_state["installation_token_requests"].append(
                        {
                            "authorization": self.headers.get("Authorization"),
                            "accept": self.headers.get("Accept"),
                        }
                    )
                    self._send_json(
                        201,
                        {
                            "token": "ghs_e2e_installation_token",
                            "expires_at": "2030-01-01T00:00:00Z",
                        },
                    )
                    return

                self._send_json(404, {"error": f"Unsupported POST path: {parsed.path}"})

            def do_PUT(self) -> None:  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                match = re.fullmatch(
                    r"/api/v3/repos/acme/mission-control/branches/([^/]+)/protection",
                    parsed.path,
                )
                if match is None:
                    self._send_json(404, {"error": f"Unsupported PUT path: {parsed.path}"})
                    return

                branch = match.group(1)
                payload = self._read_json()
                server_state["branch_protection_requests"].append(
                    {
                        "branch": branch,
                        "authorization": self.headers.get("Authorization"),
                        "payload": payload,
                    }
                )
                self._send_json(
                    200,
                    {
                        "branch": branch,
                        "enforced": True,
                        "rules": payload,
                    },
                )

            def do_GET(self) -> None:  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/api/v3/rate_limit":
                    self._send_json(200, {"rate": {"remaining": 5000}})
                    return

                if parsed.path == "/api/v3/repos/acme/mission-control/pulls":
                    server_state["pull_request_fetches"].append(
                        {
                            "authorization": self.headers.get("Authorization"),
                            "query": urllib.parse.parse_qs(parsed.query),
                        }
                    )
                    blueprint_id = server_state.get("blueprint_id") or 999999
                    self._send_json(
                        200,
                        [
                            {
                                "number": 17,
                                "title": "Blueprint release candidate",
                                "state": "open",
                                "html_url": "https://github.local/acme/mission-control/pull/17",
                                "updated_at": "2026-03-25T10:00:00Z",
                                "merged_at": None,
                                "draft": False,
                                "user": {"login": "mission-control"},
                                "head": {"ref": f"mission-control/blueprint-{blueprint_id}-plan-1-rc"},
                                "base": {"ref": "main"},
                            },
                            {
                                "number": 29,
                                "title": "Unrelated maintenance",
                                "state": "closed",
                                "html_url": "https://github.local/acme/mission-control/pull/29",
                                "updated_at": "2026-03-24T10:00:00Z",
                                "merged_at": "2026-03-24T11:00:00Z",
                                "draft": False,
                                "user": {"login": "other-user"},
                                "head": {"ref": "chore/maintenance"},
                                "base": {"ref": "main"},
                            },
                        ],
                    )
                    return

                self._send_json(404, {"error": f"Unsupported GET path: {parsed.path}"})

        return Handler


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


def validate_phase5_semiautomatic_delivery(
    base_url: str,
    fixtures_dir: Path,
    responses_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    """Validate the semi-automatic delivery slice over the public HTTP API."""

    requirements_path, roadmap_path = write_phase5_specs(fixtures_dir)
    set_fake_crewai_outputs(
        responses_path,
        [approved_review("Planning crew aprueba el plan para delivery semiautomatico.")],
    )
    blueprint = import_blueprint(base_url, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    status, plan = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        {"sprint_capacity": 12},
    )
    if status != 201:
        raise RuntimeError(f"Cannot create phase 5 scrum plan: status={status}, body={plan}")
    if plan["approval_status"] != "approved":
        raise RuntimeError(f"Phase 5 plan did not reach approved state: {plan}")

    workspace_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Mission Control E2E"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "mission-control-e2e@local"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    (workspace_root / "README.md").write_text("# Phase 5 Workspace\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "chore: initial workspace"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    status, preview = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/delivery/guardrails/preview",
        {
            "workspace_root": str(workspace_root),
        },
    )
    if status != 200:
        raise RuntimeError(f"Cannot preview phase 5 guardrails: status={status}, body={preview}")
    expected_guardrail_paths = {
        "examples/holamundo.py",
        "frontend/index.html",
        "infra/main.tf",
        "infra/outputs.tf",
        "infra/variables.tf",
    }
    if set(preview["guardrails"]["allowed_write_paths"]) != expected_guardrail_paths:
        raise RuntimeError(f"Unexpected phase 5 guardrail preview: {preview}")

    status, execution = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/delivery/execute",
        {
            "workspace_root": str(workspace_root),
            "execution_mode": "semi_automatic",
            "auto_merge_current_branch": True,
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot execute phase 5 delivery: status={status}, body={execution}")
    if execution["summary"]["ok"] is not True:
        raise RuntimeError(f"Phase 5 delivery reported validation failures: {execution}")
    if execution["review"]["verdict"] != "approved":
        raise RuntimeError(f"Phase 5 review did not approve the execution: {execution}")
    if execution["qa_gate"]["verdict"] != "passed":
        raise RuntimeError(f"Phase 5 QA gate did not pass: {execution}")
    if execution["release_candidate"]["merged"] is not True:
        raise RuntimeError(f"Phase 5 release candidate did not merge: {execution}")
    if execution["retrospective"]["item_count"] < 2:
        raise RuntimeError(f"Phase 5 retrospective did not record enough items: {execution}")

    python_script = workspace_root / "examples" / "holamundo.py"
    react_page = workspace_root / "frontend" / "index.html"
    terraform_main = workspace_root / "infra" / "main.tf"
    terraform_variables = workspace_root / "infra" / "variables.tf"
    terraform_outputs = workspace_root / "infra" / "outputs.tf"
    delivery_summary = workspace_root / ".mission_control" / "reports" / "delivery_summary.md"
    release_candidate = workspace_root / ".mission_control" / "releases" / "release_candidate.json"
    guardrail_policy = workspace_root / ".mission_control" / "guardrails" / "architecture_guardrails.json"

    for required_path in (
        python_script,
        react_page,
        terraform_main,
        terraform_variables,
        terraform_outputs,
        delivery_summary,
        release_candidate,
        guardrail_policy,
    ):
        if not required_path.is_file():
            raise RuntimeError(f"Phase 5 artifact missing from workspace: {required_path}")

    python_result = subprocess.run(
        [sys.executable, str(python_script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if python_result.returncode != 0 or python_result.stdout.strip() != "Hola Mundo":
        raise RuntimeError(
            "Phase 5 Python artifact did not execute correctly: "
            f"returncode={python_result.returncode}, stdout={python_result.stdout!r}, stderr={python_result.stderr!r}"
        )

    react_content = react_page.read_text(encoding="utf-8")
    if "createRoot" not in react_content or "Hola Mundo" not in react_content:
        raise RuntimeError(f"Phase 5 React artifact is incomplete: {react_page}")

    terraform_content = terraform_main.read_text(encoding="utf-8")
    if 'resource "aws_s3_bucket" "basic"' not in terraform_content:
        raise RuntimeError(f"Phase 5 Terraform artifact is incomplete: {terraform_main}")

    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    if current_branch.stdout.strip() != "main":
        raise RuntimeError(f"Phase 5 release flow did not restore the main branch: {current_branch.stdout!r}")

    status, report = api_call(base_url, "GET", f"/api/blueprints/{blueprint_id}/report")
    if status != 200:
        raise RuntimeError(f"Cannot read phase 5 report: status={status}, body={report}")
    if report["counts"]["artifacts"] != 11:
        raise RuntimeError(f"Unexpected phase 5 artifact count: {report}")
    if report["counts"]["retrospective_items"] != 2:
        raise RuntimeError(f"Unexpected phase 5 retrospective count: {report}")

    return {
        "blueprint_id": blueprint_id,
        "plan_id": plan["id"],
        "plan_version": plan["version"],
        "workspace_root": str(workspace_root),
        "written_file_count": execution["summary"]["written_file_count"],
        "executed_item_count": execution["summary"]["executed_item_count"],
        "artifact_count": report["counts"]["artifacts"],
        "agent_run_count": report["counts"]["agent_runs"],
        "task_execution_count": report["counts"]["task_executions"],
        "review_verdict": execution["review"]["verdict"],
        "qa_verdict": execution["qa_gate"]["verdict"],
        "release_status": execution["release_candidate"]["status"],
        "retrospective_item_count": execution["retrospective"]["item_count"],
        "guardrail_path_count": len(preview["guardrails"]["allowed_write_paths"]),
    }


def validate_phase6_operator_control(
    base_url: str,
    fixtures_dir: Path,
    responses_path: Path,
    github_api_url: str,
    github_state: dict[str, Any],
) -> dict[str, Any]:
    """Validate operator control, GitHub sync, and blueprint observability over the public HTTP API."""

    status, dashboard = api_call(base_url, "GET", "/api/operator/dashboard")
    if status != 200:
        raise RuntimeError(f"Cannot read operator dashboard: status={status}, body={dashboard}")
    if "providers" not in dashboard or "settings" not in dashboard or "overview" not in dashboard:
        raise RuntimeError(f"Operator dashboard payload is incomplete: {dashboard}")

    private_key_pem = generate_github_app_private_key_pem()
    status, updated = api_call(
        base_url,
        "PUT",
        "/api/operator/settings",
        {
            "ollama": {
                "base_url": "http://operator-ollama:11434",
                "default_model": "qwen2.5-coder:operator",
            },
            "bedrock": {
                "region": "us-east-1",
                "planner_model": "anthropic.claude-3-7-sonnet",
                "reviewer_model": "anthropic.claude-3-5-sonnet",
            },
            "github": {
                "api_url": github_api_url,
                "repository": "acme/mission-control",
                "default_base_branch": "main",
                "protected_branches": ["main", "release"],
                "required_approving_review_count": 2,
                "app_id": 12345,
                "app_installation_id": 98765,
                "app_private_key": private_key_pem,
            },
        },
    )
    if status != 200:
        raise RuntimeError(f"Cannot update operator settings: status={status}, body={updated}")
    if updated["settings"]["ollama"]["base_url"] != "http://operator-ollama:11434":
        raise RuntimeError(f"Operator dashboard did not apply Ollama override: {updated}")
    if updated["settings"]["github"]["protected_branches"] != ["main", "release"]:
        raise RuntimeError(f"Operator dashboard did not persist GitHub branch policy: {updated}")
    if updated["settings"]["github"]["auth_mode"] != "app":
        raise RuntimeError(f"Operator dashboard did not switch GitHub auth mode to app: {updated}")
    if updated["providers"]["github"]["ok"] is not True:
        raise RuntimeError(f"GitHub provider should be healthy in app mode: {updated}")
    if updated["runtime_config_applied"] is not True:
        raise RuntimeError(f"Runtime did not reload operator settings: {updated}")

    status, settings = api_call(base_url, "GET", "/api/operator/settings")
    if status != 200:
        raise RuntimeError(f"Cannot read operator settings: status={status}, body={settings}")
    if settings["github"]["token_configured"] is not False:
        raise RuntimeError(f"Operator settings should keep GitHub token cleared in E2E: {settings}")
    if settings["github"]["app_private_key_configured"] is not True:
        raise RuntimeError(f"Operator settings should persist GitHub App key: {settings}")

    status, github_dashboard = api_call(base_url, "GET", "/api/operator/github/dashboard")
    if status != 200:
        raise RuntimeError(f"Cannot read operator GitHub dashboard: status={status}, body={github_dashboard}")
    if github_dashboard["auth_mode"] != "app":
        raise RuntimeError(f"GitHub dashboard should expose app auth mode: {github_dashboard}")
    if github_dashboard["required_approving_review_count"] != 2:
        raise RuntimeError(f"GitHub dashboard lost review settings: {github_dashboard}")

    requirements_path, roadmap_path = write_phase6_specs(fixtures_dir)
    set_fake_crewai_outputs(
        responses_path,
        [approved_review("Planning crew aprueba el plan de observabilidad GitHub.")],
    )
    blueprint = import_blueprint(base_url, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]
    github_state["blueprint_id"] = blueprint_id

    status, feedback = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/feedback",
        {
            "stage_name": "review",
            "status": "approved",
            "source": "operator",
            "feedback_text": "PR visibility aprobada para merge.",
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot persist phase 6 feedback: status={status}, body={feedback}")

    status, retrospective = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/retrospective-items",
        {
            "category": "win",
            "summary": "Timeline GitHub visible por blueprint.",
            "action_item": "Mantener sync de PRs en dashboard.",
            "owner": "Jarvis-PM",
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot persist phase 6 retrospective item: status={status}, body={retrospective}")

    status, agent_run = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/agent-runs",
        {
            "agent_name": "github_sync_agent",
            "agent_role": "release",
            "provider": "github",
            "model": "api",
            "status": "completed",
            "input_summary": "Sync pull requests",
            "output_summary": "Pull requests fetched",
            "completed": True,
        },
    )
    if status != 201:
        raise RuntimeError(f"Cannot persist phase 6 agent run: status={status}, body={agent_run}")

    status, plan = api_call(
        base_url,
        "POST",
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        {"sprint_capacity": 6},
    )
    if status != 201:
        raise RuntimeError(f"Cannot create phase 6 scrum plan: status={status}, body={plan}")
    if plan["approval_status"] != "approved":
        raise RuntimeError(f"Phase 6 plan did not reach approved state: {plan}")

    status, branch_sync = api_call(base_url, "POST", "/api/operator/github/sync-branches", {})
    if status != 200:
        raise RuntimeError(f"Cannot sync protected branches: status={status}, body={branch_sync}")
    if branch_sync["branch_count"] != 2:
        raise RuntimeError(f"Unexpected protected branch sync result: {branch_sync}")
    if len(github_state["installation_token_requests"]) != 1:
        raise RuntimeError(f"GitHub App token exchange did not happen exactly once: {github_state}")
    if len(github_state["branch_protection_requests"]) != 2:
        raise RuntimeError(f"Expected two branch protection requests: {github_state}")

    branch_payloads = {
        item["branch"]: item["payload"] for item in github_state["branch_protection_requests"]
    }
    for branch in ("main", "release"):
        payload = branch_payloads.get(branch)
        if payload is None:
            raise RuntimeError(f"Missing branch protection payload for {branch}: {github_state}")
        if payload["required_pull_request_reviews"]["required_approving_review_count"] != 2:
            raise RuntimeError(f"Unexpected branch protection review policy: {payload}")

    status, pull_request_sync = api_call(
        base_url,
        "POST",
        "/api/operator/github/pull-requests/sync",
        {"state": "all", "per_page": 20},
    )
    if status != 200:
        raise RuntimeError(f"Cannot sync GitHub pull requests: status={status}, body={pull_request_sync}")
    if pull_request_sync["pull_request_count"] != 2:
        raise RuntimeError(f"Unexpected PR sync result: {pull_request_sync}")
    if len(github_state["installation_token_requests"]) != 1:
        raise RuntimeError(f"GitHub App token should have been cached after branch sync: {github_state}")
    if len(github_state["pull_request_fetches"]) != 1:
        raise RuntimeError(f"Expected one PR fetch against fake GitHub: {github_state}")

    status, timeline = api_call(base_url, "GET", "/api/operator/github/timeline")
    if status != 200:
        raise RuntimeError(f"Cannot read operator GitHub timeline: status={status}, body={timeline}")
    if len(timeline["events"]) < 4:
        raise RuntimeError(f"Timeline should contain branch + PR sync events: {timeline}")

    status, blueprint_timeline = api_call(
        base_url,
        "GET",
        f"/api/operator/github/timeline?blueprint_id={blueprint_id}",
    )
    if status != 200:
        raise RuntimeError(f"Cannot read blueprint GitHub timeline: status={status}, body={blueprint_timeline}")
    if len(blueprint_timeline["events"]) != 1:
        raise RuntimeError(f"Expected a single blueprint-linked PR event: {blueprint_timeline}")

    status, blueprint_dashboard = api_call(
        base_url,
        "GET",
        f"/api/blueprints/{blueprint_id}/operator-dashboard",
    )
    if status != 200:
        raise RuntimeError(
            f"Cannot read blueprint operator dashboard: status={status}, body={blueprint_dashboard}"
        )
    if blueprint_dashboard["report"]["counts"]["github_sync_events"] != 1:
        raise RuntimeError(f"Blueprint dashboard lost GitHub sync event linkage: {blueprint_dashboard}")
    if not any(
        item.get("source") == "operator" and item.get("stage_name") == "review"
        for item in blueprint_dashboard["recent_feedback"]
    ):
        raise RuntimeError(f"Blueprint dashboard lost operator review feedback: {blueprint_dashboard}")
    if len(blueprint_dashboard["retrospective_items"]) != 1:
        raise RuntimeError(f"Blueprint dashboard lost retrospective item: {blueprint_dashboard}")
    if len(blueprint_dashboard["recent_agent_runs"]) < 1:
        raise RuntimeError(f"Blueprint dashboard should expose agent runs: {blueprint_dashboard}")
    if blueprint_dashboard["latest_plan"] is None:
        raise RuntimeError(f"Blueprint dashboard should expose latest scrum plan: {blueprint_dashboard}")
    if [item["number"] for item in blueprint_dashboard["github"]["pull_requests"]] != [17]:
        raise RuntimeError(f"Blueprint dashboard should expose the linked PR only: {blueprint_dashboard}")

    return {
        "blueprint_id": blueprint_id,
        "repository": settings["github"]["repository"],
        "default_base_branch": settings["github"]["default_base_branch"],
        "protected_branches": settings["github"]["protected_branches"],
        "auth_mode": settings["github"]["auth_mode"],
        "runtime_config_applied": updated["runtime_config_applied"],
        "branch_sync_count": branch_sync["branch_count"],
        "pull_request_sync_count": pull_request_sync["pull_request_count"],
        "github_timeline_event_count": len(timeline["events"]),
        "blueprint_pull_request_count": len(blueprint_dashboard["github"]["pull_requests"]),
        "blueprint_feedback_count": len(blueprint_dashboard["recent_feedback"]),
        "blueprint_retrospective_count": len(blueprint_dashboard["retrospective_items"]),
        "blueprint_agent_run_count": len(blueprint_dashboard["recent_agent_runs"]),
        "github_app_token_exchanges": len(github_state["installation_token_requests"]),
        "provider_names": sorted(updated["providers"].keys()),
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
        phase5_workspace = temp_root / "phase5_workspace"
        fake_github = FakeGitHubServer()
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
            phase5_result = validate_phase5_semiautomatic_delivery(
                base_url,
                fixtures_dir,
                responses_path,
                phase5_workspace,
            )
            phase6_result = validate_phase6_operator_control(
                base_url,
                fixtures_dir,
                responses_path,
                fake_github.api_url,
                fake_github.state,
            )
            langgraph_result = validate_langgraph_wiring(args.allow_missing_langgraph)

            print(
                json.dumps(
                    {
                        "mission_control_e2e": "ok",
                        "base_url": base_url,
                        "three_agent_flow": api_result,
                        "phase4_scrum_flow": phase4_result,
                        "phase5_semiautomatic_delivery": phase5_result,
                        "phase6_operator_control": phase6_result,
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
            fake_github.close()


if __name__ == "__main__":
    raise SystemExit(main())
