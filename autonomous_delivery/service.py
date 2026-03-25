from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomous_scrum import AutonomousScrumPlannerService
from database import (
    AgentRunRecord,
    DeliveryTaskRecord,
    ScrumPlanItemRecord,
    ScrumPlanRecord,
    TaskExecutionRecord,
    db,
)
from delivery_tracking import DeliveryTrackingService


SUPPORTED_EXECUTION_MODES = {"semi_automatic"}
DELIVERY_SOURCE = "semi_automatic_delivery"


@dataclass(frozen=True)
class DeliveryFileSpec:
    path: str
    content: str
    artifact_type: str


@dataclass(frozen=True)
class DeliveryRecipe:
    name: str
    summary: str
    files: tuple[DeliveryFileSpec, ...]
    validation_kind: str


class AutonomousDeliveryService:
    """Executes simple ready tickets into a target workspace in semi-automatic mode."""

    def __init__(self, default_workspace_root: str | Path):
        self.default_workspace_root = Path(default_workspace_root).expanduser().resolve()
        self.tracking_service = DeliveryTrackingService()
        self.scrum_planner_service = AutonomousScrumPlannerService()

    def execute_plan(
        self,
        *,
        blueprint_id: int,
        workspace_root: str | Path | None = None,
        plan_id: int | None = None,
        sprint_order: int | None = None,
        item_limit: int | None = None,
        ticket_ids: list[str] | None = None,
        execution_mode: str = "semi_automatic",
    ) -> dict[str, Any]:
        normalized_mode = execution_mode.strip().lower()
        if normalized_mode not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")

        workspace = self._resolve_workspace_root(workspace_root)
        plan = self.scrum_planner_service.get_plan(
            blueprint_id,
            plan_id=plan_id,
            status="latest" if plan_id is None else None,
        )
        if plan.approval_status != "approved":
            raise RuntimeError("Scrum plan must be approved before delivery execution.")

        selected_items = self._select_items(
            plan=plan,
            sprint_order=sprint_order,
            item_limit=item_limit,
            ticket_ids=ticket_ids,
        )
        if not selected_items:
            raise RuntimeError("No ready planned items found for semi-automatic delivery.")
        self._ensure_supported_items(selected_items)

        execution_started = self.tracking_service.create_stage_event(
            blueprint_id=blueprint_id,
            stage_name="execution",
            status="in_progress",
            source=DELIVERY_SOURCE,
            summary=(
                f"Starting semi-automatic delivery for scrum plan v{plan.version} "
                f"into {workspace}"
            ),
            metadata={
                "scrum_plan_id": plan.id,
                "scrum_plan_version": plan.version,
                "workspace_root": str(workspace),
                "execution_mode": normalized_mode,
                "selected_ticket_ids": [item.delivery_task.ticket_id for item in selected_items if item.delivery_task],
            },
        )

        execution_payloads: list[dict[str, Any]] = []
        written_file_count = 0
        validation_failures = 0
        for item in selected_items:
            execution_payload = self._execute_item(
                blueprint_id=blueprint_id,
                item=item,
                workspace_root=workspace,
                execution_mode=normalized_mode,
            )
            execution_payloads.append(execution_payload)
            written_file_count += len(execution_payload["files"])
            if execution_payload["validation"]["ok"] is not True:
                validation_failures += 1

        execution_status = "completed" if validation_failures == 0 else "failed"
        qa_status = "completed" if validation_failures == 0 else "failed"

        self.tracking_service.create_stage_event(
            blueprint_id=blueprint_id,
            stage_name="execution",
            status=execution_status,
            source=DELIVERY_SOURCE,
            summary=(
                f"Semi-automatic delivery finished with status={execution_status} "
                f"for scrum plan v{plan.version}."
            ),
            metadata={
                "scrum_plan_id": plan.id,
                "workspace_root": str(workspace),
                "execution_started_event_id": execution_started.id,
                "written_file_count": written_file_count,
                "validation_failures": validation_failures,
            },
        )
        self.tracking_service.create_stage_event(
            blueprint_id=blueprint_id,
            stage_name="qa_gate",
            status=qa_status,
            source=DELIVERY_SOURCE,
            summary=(
                f"Semi-automatic QA gate finished with status={qa_status} "
                f"for scrum plan v{plan.version}."
            ),
            metadata={
                "scrum_plan_id": plan.id,
                "workspace_root": str(workspace),
                "validation_failures": validation_failures,
                "validated_ticket_ids": [
                    item["ticket_id"] for item in execution_payloads
                ],
            },
        )

        return {
            "blueprint_id": blueprint_id,
            "plan_id": plan.id,
            "plan_version": plan.version,
            "approval_status": plan.approval_status,
            "execution_mode": normalized_mode,
            "workspace_root": str(workspace),
            "summary": {
                "selected_item_count": len(selected_items),
                "executed_item_count": len(execution_payloads),
                "written_file_count": written_file_count,
                "validation_failures": validation_failures,
                "ok": validation_failures == 0,
            },
            "executions": execution_payloads,
        }

    def _select_items(
        self,
        *,
        plan: ScrumPlanRecord,
        sprint_order: int | None,
        item_limit: int | None,
        ticket_ids: list[str] | None,
    ) -> list[ScrumPlanItemRecord]:
        normalized_ticket_ids = {
            ticket_id.strip()
            for ticket_id in ticket_ids or []
            if isinstance(ticket_id, str) and ticket_id.strip()
        }
        items = sorted(
            list(plan.items),
            key=lambda item: (
                item.sprint_order if item.sprint_order is not None else 9999,
                item.sequence_index,
            ),
        )
        filtered = [
            item
            for item in items
            if item.plan_status == "planned"
            and item.readiness_status == "ready"
            and item.delivery_task is not None
            and (sprint_order is None or item.sprint_order == sprint_order)
            and (
                not normalized_ticket_ids
                or item.delivery_task.ticket_id in normalized_ticket_ids
            )
        ]
        if item_limit is not None:
            if item_limit <= 0:
                raise ValueError("item_limit must be positive")
            filtered = filtered[:item_limit]
        return filtered

    def _execute_item(
        self,
        *,
        blueprint_id: int,
        item: ScrumPlanItemRecord,
        workspace_root: Path,
        execution_mode: str,
    ) -> dict[str, Any]:
        task = item.delivery_task
        assert task is not None
        recipe = self._resolve_recipe(task)

        agent_run = self.tracking_service.create_agent_run(
            blueprint_id=blueprint_id,
            agent_name="semi_automatic_delivery",
            agent_role="delivery",
            provider="mission_control",
            model=recipe.name,
            status="running",
            input_summary=(
                f"{task.ticket_id}: {task.title} -> workspace={workspace_root}"
            ),
            runtime_name=execution_mode,
        )
        task_execution = self.tracking_service.create_task_execution(
            blueprint_id=blueprint_id,
            delivery_task_id=task.id,
            agent_run_id=agent_run.id,
            status="in_progress",
            attempt_number=1,
            summary=f"Applying recipe {recipe.name}",
        )

        try:
            written_paths = self._write_recipe_files(workspace_root=workspace_root, recipe=recipe)
            artifact_payloads = []
            for file_spec, written_path in zip(recipe.files, written_paths):
                artifact = self.tracking_service.create_artifact(
                    blueprint_id=blueprint_id,
                    agent_run_id=agent_run.id,
                    task_execution_id=task_execution.id,
                    name=written_path.name,
                    artifact_type=file_spec.artifact_type,
                    uri=str(written_path),
                    metadata={
                        "recipe": recipe.name,
                        "ticket_id": task.ticket_id,
                        "workspace_root": str(workspace_root),
                    },
                )
                artifact_payloads.append(artifact.to_dict())

            validation = self._validate_recipe(
                recipe=recipe,
                workspace_root=workspace_root,
            )
            summary = (
                f"{recipe.summary} Wrote {len(written_paths)} file(s) "
                f"for {task.ticket_id}."
            )
            self._complete_records(
                agent_run=agent_run,
                task_execution=task_execution,
                success=validation["ok"],
                summary=summary,
                error_message=None if validation["ok"] else validation.get("stderr") or validation.get("summary"),
            )
            return {
                "ticket_id": task.ticket_id,
                "title": task.title,
                "recipe": recipe.name,
                "status": "done" if validation["ok"] else "failed",
                "agent_run_id": agent_run.id,
                "task_execution_id": task_execution.id,
                "files": [str(path.relative_to(workspace_root)) for path in written_paths],
                "artifacts": artifact_payloads,
                "validation": validation,
            }
        except Exception as exc:
            self._complete_records(
                agent_run=agent_run,
                task_execution=task_execution,
                success=False,
                summary=f"Failed to execute recipe {recipe.name} for {task.ticket_id}.",
                error_message=str(exc),
            )
            return {
                "ticket_id": task.ticket_id,
                "title": task.title,
                "recipe": recipe.name,
                "status": "failed",
                "agent_run_id": agent_run.id,
                "task_execution_id": task_execution.id,
                "files": [],
                "artifacts": [],
                "validation": {
                    "kind": recipe.validation_kind,
                    "ok": False,
                    "summary": str(exc),
                    "stderr": str(exc),
                },
            }

    def _resolve_workspace_root(self, raw_workspace_root: str | Path | None) -> Path:
        candidate = Path(raw_workspace_root or self.default_workspace_root).expanduser()
        if not candidate.is_absolute():
            candidate = self.default_workspace_root / candidate
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate.resolve()

    def _resolve_recipe(self, task: DeliveryTaskRecord) -> DeliveryRecipe:
        normalized = self._normalize_text(
            " ".join(
                filter(
                    None,
                    [
                        task.ticket_id,
                        task.title,
                        task.description or "",
                        " ".join(task.acceptance_criteria_json or []),
                    ],
                )
            )
        )

        if "holamundo.py" in normalized or (
            "python" in normalized and "hola mundo" in normalized and "examples" in normalized
        ):
            return DeliveryRecipe(
                name="python_hello_world",
                summary="Created the requested Python hello-world script.",
                files=(
                    DeliveryFileSpec(
                        path="examples/holamundo.py",
                        artifact_type="code",
                        content=(
                            "def main() -> None:\n"
                            '    print("Hola Mundo")\n'
                            "\n"
                            'if __name__ == "__main__":\n'
                            "    main()\n"
                        ),
                    ),
                ),
                validation_kind="command",
            )

        if "react" in normalized and ("frontend" in normalized or "frotend" in normalized):
            return DeliveryRecipe(
                name="react_hello_world",
                summary="Created the requested React hello-world page.",
                files=(
                    DeliveryFileSpec(
                        path="frontend/index.html",
                        artifact_type="frontend",
                        content=(
                            "<!doctype html>\n"
                            '<html lang="es">\n'
                            "  <head>\n"
                            '    <meta charset="UTF-8" />\n'
                            '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
                            "    <title>Hola Mundo React</title>\n"
                            "    <style>\n"
                            "      body {\n"
                            "        margin: 0;\n"
                            "        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;\n"
                            "        background: linear-gradient(135deg, #f5efe6, #dce8f2);\n"
                            "      }\n"
                            "      main {\n"
                            "        min-height: 100vh;\n"
                            "        display: grid;\n"
                            "        place-items: center;\n"
                            "        color: #153243;\n"
                            "      }\n"
                            "      .card {\n"
                            "        padding: 2rem 2.5rem;\n"
                            "        border-radius: 18px;\n"
                            "        background: rgba(255, 255, 255, 0.9);\n"
                            "        box-shadow: 0 24px 60px rgba(21, 50, 67, 0.16);\n"
                            "      }\n"
                            "      h1 {\n"
                            "        margin: 0;\n"
                            "        font-size: clamp(2rem, 5vw, 3.5rem);\n"
                            "      }\n"
                            "    </style>\n"
                            "  </head>\n"
                            "  <body>\n"
                            '    <div id="root"></div>\n'
                            '    <script type="module">\n'
                            "      import React from 'https://esm.sh/react@18';\n"
                            "      import { createRoot } from 'https://esm.sh/react-dom@18/client';\n"
                            "\n"
                            "      function App() {\n"
                            "        return React.createElement(\n"
                            "          'main',\n"
                            "          null,\n"
                            "          React.createElement(\n"
                            "            'section',\n"
                            "            { className: 'card' },\n"
                            "            React.createElement('h1', null, 'Hola Mundo')\n"
                            "          )\n"
                            "        );\n"
                            "      }\n"
                            "\n"
                            "      createRoot(document.getElementById('root')).render(\n"
                            "        React.createElement(App)\n"
                            "      );\n"
                            "    </script>\n"
                            "  </body>\n"
                            "</html>\n"
                        ),
                    ),
                ),
                validation_kind="static_check",
            )

        if "terraform" in normalized and "infra" in normalized and "s3" in normalized:
            return DeliveryRecipe(
                name="terraform_s3_module",
                summary="Created the requested Terraform S3 module.",
                files=(
                    DeliveryFileSpec(
                        path="infra/main.tf",
                        artifact_type="iac",
                        content=(
                            "terraform {\n"
                            '  required_version = ">= 1.5.0"\n'
                            "\n"
                            "  required_providers {\n"
                            "    aws = {\n"
                            '      source  = "hashicorp/aws"\n'
                            '      version = ">= 5.0"\n'
                            "    }\n"
                            "  }\n"
                            "}\n"
                            "\n"
                            'resource "aws_s3_bucket" "basic" {\n'
                            "  bucket = var.bucket_name\n"
                            "\n"
                            "  tags = {\n"
                            "    Name      = var.bucket_name\n"
                            '    ManagedBy = "mission-control"\n'
                            "  }\n"
                            "}\n"
                        ),
                    ),
                    DeliveryFileSpec(
                        path="infra/variables.tf",
                        artifact_type="iac",
                        content=(
                            'variable "bucket_name" {\n'
                            '  description = "Nombre del bucket S3 a crear."\n'
                            "  type        = string\n"
                            "}\n"
                        ),
                    ),
                    DeliveryFileSpec(
                        path="infra/outputs.tf",
                        artifact_type="iac",
                        content=(
                            'output "bucket_arn" {\n'
                            '  description = "ARN del bucket S3 creado por el modulo."\n'
                            "  value       = aws_s3_bucket.basic.arn\n"
                            "}\n"
                        ),
                    ),
                ),
                validation_kind="command_or_static_check",
            )

        raise RuntimeError(
            f"No semi-automatic recipe available for {task.ticket_id}: {task.title}"
        )

    def _write_recipe_files(
        self,
        *,
        workspace_root: Path,
        recipe: DeliveryRecipe,
    ) -> list[Path]:
        written_paths: list[Path] = []
        for file_spec in recipe.files:
            output_path = (workspace_root / file_spec.path).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(file_spec.content, encoding="utf-8")
            written_paths.append(output_path)
        return written_paths

    def _validate_recipe(
        self,
        *,
        recipe: DeliveryRecipe,
        workspace_root: Path,
    ) -> dict[str, Any]:
        if recipe.name == "python_hello_world":
            completed = subprocess.run(
                ["python3", "examples/holamundo.py"],
                cwd=workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            ok = completed.returncode == 0 and completed.stdout.strip() == "Hola Mundo"
            return {
                "kind": "command",
                "command": "python3 examples/holamundo.py",
                "ok": ok,
                "exit_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "summary": "Python hello-world script executed successfully." if ok else "Python validation failed.",
            }

        if recipe.name == "react_hello_world":
            content = (workspace_root / "frontend" / "index.html").read_text(encoding="utf-8")
            ok = "createRoot" in content and "Hola Mundo" in content and "https://esm.sh/react@18" in content
            return {
                "kind": "static_check",
                "ok": ok,
                "checks": [
                    "frontend/index.html contains a React root mount.",
                    "frontend/index.html renders the Hola Mundo greeting.",
                ],
                "summary": "React page scaffold validated by static checks." if ok else "React static validation failed.",
            }

        if recipe.name == "terraform_s3_module":
            terraform_binary = shutil.which("terraform")
            if terraform_binary is not None:
                completed = subprocess.run(
                    [terraform_binary, "fmt", "-check"],
                    cwd=workspace_root / "infra",
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                ok = completed.returncode == 0
                return {
                    "kind": "command",
                    "command": "terraform fmt -check",
                    "ok": ok,
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout.strip(),
                    "stderr": completed.stderr.strip(),
                    "summary": "Terraform module formatted and validated with terraform fmt." if ok else "Terraform fmt validation failed.",
                }

            content = (workspace_root / "infra" / "main.tf").read_text(encoding="utf-8")
            ok = 'resource "aws_s3_bucket" "basic"' in content and "bucket = var.bucket_name" in content
            return {
                "kind": "static_check",
                "ok": ok,
                "checks": [
                    "infra/main.tf declares aws_s3_bucket.basic.",
                    "infra/main.tf uses var.bucket_name.",
                ],
                "summary": "Terraform module validated by static checks because terraform is not installed." if ok else "Terraform static validation failed.",
            }

        raise RuntimeError(f"Unsupported recipe validation: {recipe.name}")

    def _ensure_supported_items(self, items: list[ScrumPlanItemRecord]) -> None:
        unsupported_items: list[str] = []
        for item in items:
            task = item.delivery_task
            if task is None:
                continue
            try:
                self._resolve_recipe(task)
            except RuntimeError:
                unsupported_items.append(f"{task.ticket_id}: {task.title}")
        if unsupported_items:
            raise RuntimeError(
                "Semi-automatic delivery only supports recipe-backed tickets. "
                f"Unsupported items: {', '.join(unsupported_items)}"
            )

    @staticmethod
    def _complete_records(
        *,
        agent_run: AgentRunRecord,
        task_execution: TaskExecutionRecord,
        success: bool,
        summary: str,
        error_message: str | None,
    ) -> None:
        completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        agent_run.status = "completed" if success else "failed"
        agent_run.output_summary = summary
        agent_run.error_message = error_message
        agent_run.completed_at = completed_at

        task_execution.status = "done" if success else "failed"
        task_execution.summary = summary
        task_execution.error_message = error_message
        task_execution.completed_at = completed_at
        db.session.commit()

    @staticmethod
    def _normalize_text(raw_value: str) -> str:
        return " ".join(
            raw_value.lower().replace("_", " ").replace("-", " ").split()
        )
