from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from architecture_guardrails import (
    DEFAULT_POLICY_RELATIVE_PATH,
    ArchitectureGuardrailPolicy,
    assert_allowed_paths,
    merge_project_guardrails,
    save_guardrail_policy,
    validate_relative_path,
    validate_unix_command,
)
from autonomous_scrum import AutonomousScrumPlannerService
from database import (
    AgentRunRecord,
    DeliveryTaskRecord,
    ScrumPlanItemRecord,
    ScrumPlanRecord,
    SprintCycleRecord,
    TaskExecutionRecord,
    db,
)
from delivery_tracking import DeliveryTrackingService
from spec_intake import BlueprintPersistenceService


SUPPORTED_EXECUTION_MODES = {"semi_automatic"}
DELIVERY_SOURCE = "semi_automatic_delivery"
INTERNAL_GUARDRAIL_WRITE_ROOTS = (
    ".mission_control/reports/",
    ".mission_control/releases/",
    ".mission_control/guardrails/",
)


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
        self.blueprint_persistence_service = BlueprintPersistenceService()

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
        auto_merge_current_branch: bool = False,
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
        guardrail_context = self._prepare_guardrails(
            blueprint_id=blueprint_id,
            plan=plan,
            workspace_root=workspace,
            selected_items=selected_items,
            persist=True,
        )
        guardrail_policy = guardrail_context["policy"]
        selected_sprint_cycles = self._resolve_selected_sprint_cycles(selected_items)
        self._update_sprint_statuses(selected_sprint_cycles, status="active")

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
                "guardrail_policy_path": guardrail_context["policy_path"],
            },
        )

        execution_payloads: list[dict[str, Any]] = []
        generated_artifacts: list[dict[str, Any]] = []
        for item in selected_items:
            execution_payload = self._execute_item(
                blueprint_id=blueprint_id,
                item=item,
                workspace_root=workspace,
                execution_mode=normalized_mode,
                guardrail_policy=guardrail_policy,
            )
            execution_payloads.append(execution_payload)
            generated_artifacts.extend(execution_payload["artifacts"])

        written_file_count = sum(len(item["files"]) for item in execution_payloads)
        validation_failures = sum(
            1 for item in execution_payloads if item["validation"]["ok"] is not True
        )
        review_result = self._run_review_stage(
            blueprint_id=blueprint_id,
            plan=plan,
            workspace_root=workspace,
            execution_payloads=execution_payloads,
        )
        qa_gate_result = self._run_qa_gate(
            blueprint_id=blueprint_id,
            plan=plan,
            workspace_root=workspace,
            execution_payloads=execution_payloads,
            review_result=review_result,
        )
        artifact_builder_result = self._build_supporting_artifacts(
            blueprint_id=blueprint_id,
            plan=plan,
            workspace_root=workspace,
            execution_payloads=execution_payloads,
            review_result=review_result,
            qa_gate_result=qa_gate_result,
            guardrail_policy=guardrail_policy,
        )
        release_result = self._create_release_candidate(
            blueprint_id=blueprint_id,
            plan=plan,
            workspace_root=workspace,
            generated_artifacts=generated_artifacts,
            supporting_artifacts=artifact_builder_result["artifacts"],
            qa_gate_result=qa_gate_result,
            auto_merge_current_branch=auto_merge_current_branch,
            guardrail_policy=guardrail_policy,
        )
        retrospective_result = self._close_sprint_and_record_retro(
            blueprint_id=blueprint_id,
            plan=plan,
            workspace_root=workspace,
            selected_sprint_cycles=selected_sprint_cycles,
            execution_payloads=execution_payloads,
            review_result=review_result,
            qa_gate_result=qa_gate_result,
            release_result=release_result,
            guardrail_policy=guardrail_policy,
        )

        execution_status = "completed" if validation_failures == 0 else "failed"

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

        return {
            "blueprint_id": blueprint_id,
            "plan_id": plan.id,
            "plan_version": plan.version,
            "approval_status": plan.approval_status,
            "execution_mode": normalized_mode,
            "workspace_root": str(workspace),
            "guardrails": self._serialize_guardrail_context(
                policy=guardrail_policy,
                policy_path=guardrail_context["policy_path"],
                persisted=True,
                project_guardrails=guardrail_context["project_guardrails"],
            ),
            "summary": {
                "selected_item_count": len(selected_items),
                "executed_item_count": len(execution_payloads),
                "written_file_count": written_file_count,
                "validation_failures": validation_failures,
                "review_verdict": review_result["verdict"],
                "qa_verdict": qa_gate_result["verdict"],
                "release_status": release_result["status"],
                "retrospective_item_count": retrospective_result["item_count"],
                "ok": (
                    validation_failures == 0
                    and review_result["approved"] is True
                    and qa_gate_result["passed"] is True
                    and release_result["ok"] is True
                ),
            },
            "executions": execution_payloads,
            "review": review_result,
            "qa_gate": qa_gate_result,
            "artifact_builder": artifact_builder_result,
            "release_candidate": release_result,
            "retrospective": retrospective_result,
        }

    def preview_guardrails(
        self,
        *,
        blueprint_id: int,
        workspace_root: str | Path | None = None,
        plan_id: int | None = None,
        sprint_order: int | None = None,
        item_limit: int | None = None,
        ticket_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        workspace = self._resolve_workspace_root(workspace_root)
        plan = self.scrum_planner_service.get_plan(
            blueprint_id,
            plan_id=plan_id,
            status="latest" if plan_id is None else None,
        )
        selected_items = self._select_items(
            plan=plan,
            sprint_order=sprint_order,
            item_limit=item_limit,
            ticket_ids=ticket_ids,
        )
        if not selected_items:
            raise RuntimeError("No ready planned items found to build architecture guardrails.")
        self._ensure_supported_items(selected_items)
        guardrail_context = self._prepare_guardrails(
            blueprint_id=blueprint_id,
            plan=plan,
            workspace_root=workspace,
            selected_items=selected_items,
            persist=False,
        )
        return {
            "blueprint_id": blueprint_id,
            "plan_id": plan.id,
            "plan_version": plan.version,
            "approval_status": plan.approval_status,
            "workspace_root": str(workspace),
            "selected_item_count": len(selected_items),
            "selected_ticket_ids": [
                item.delivery_task.ticket_id
                for item in selected_items
                if item.delivery_task is not None
            ],
            "guardrails": self._serialize_guardrail_context(
                policy=guardrail_context["policy"],
                policy_path=guardrail_context["policy_path"],
                persisted=False,
                project_guardrails=guardrail_context["project_guardrails"],
            ),
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

    def _prepare_guardrails(
        self,
        *,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        workspace_root: Path,
        selected_items: list[ScrumPlanItemRecord],
        persist: bool,
    ) -> dict[str, Any]:
        policy = self._build_guardrail_policy(
            blueprint_id=blueprint_id,
            plan=plan,
            selected_items=selected_items,
        )
        policy_path = workspace_root / DEFAULT_POLICY_RELATIVE_PATH
        if persist:
            saved_path = save_guardrail_policy(workspace_root, policy)
            policy_path = saved_path
        return {
            "policy": policy,
            "policy_path": str(policy_path.resolve()),
            "project_guardrails": (
                dict(getattr(plan.blueprint, "delivery_guardrails_json", {}) or {})
                if plan.blueprint is not None
                else {}
            ),
        }

    def _build_guardrail_policy(
        self,
        *,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        selected_items: list[ScrumPlanItemRecord],
    ) -> ArchitectureGuardrailPolicy:
        allowed_write_paths: set[str] = set()
        ticket_ids: list[str] = []
        recipe_names: list[str] = []

        for item in selected_items:
            task = item.delivery_task
            if task is None:
                continue
            recipe = self._resolve_recipe(task)
            ticket_ids.append(task.ticket_id)
            recipe_names.append(recipe.name)
            for file_spec in recipe.files:
                allowed_write_paths.add(file_spec.path)

        policy = ArchitectureGuardrailPolicy.from_dict(
            {
                "scope": {
                    "kind": "semi_automatic_delivery",
                    "blueprint_id": blueprint_id,
                    "scrum_plan_id": plan.id,
                    "scrum_plan_version": plan.version,
                    "approval_status": plan.approval_status,
                    "ticket_ids": ticket_ids,
                    "recipes": recipe_names,
                },
                "allowed_write_paths": sorted(allowed_write_paths),
                "allowed_write_roots": list(INTERNAL_GUARDRAIL_WRITE_ROOTS),
            }
        )
        project_guardrails = (
            dict(getattr(plan.blueprint, "delivery_guardrails_json", {}) or {})
            if plan.blueprint is not None
            else {}
        )
        policy = merge_project_guardrails(policy, project_guardrails)
        assert_allowed_paths(list(policy.allowed_write_paths), policy)
        return policy

    @staticmethod
    def _serialize_guardrail_context(
        *,
        policy: ArchitectureGuardrailPolicy,
        policy_path: str,
        persisted: bool,
        project_guardrails: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "persisted": persisted,
            "policy_path": policy_path,
            "policy_relative_path": DEFAULT_POLICY_RELATIVE_PATH,
            "scope": policy.scope,
            "allowed_write_paths": list(policy.allowed_write_paths),
            "allowed_write_roots": list(policy.allowed_write_roots),
            "forbidden_path_prefixes": list(policy.forbidden_path_prefixes),
            "forbidden_path_globs": list(policy.forbidden_path_globs),
            "forbidden_command_patterns": list(policy.forbidden_command_patterns),
            "project_guardrails": dict(project_guardrails or {}),
        }

    def _execute_item(
        self,
        *,
        blueprint_id: int,
        item: ScrumPlanItemRecord,
        workspace_root: Path,
        execution_mode: str,
        guardrail_policy: ArchitectureGuardrailPolicy,
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
            written_paths = self._write_recipe_files(
                workspace_root=workspace_root,
                recipe=recipe,
                guardrail_policy=guardrail_policy,
            )
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
            attempts = [
                {
                    "attempt_number": 1,
                    "validation": validation,
                    "autocorrection_applied": False,
                }
            ]
            final_task_execution = task_execution
            autocorrection = {
                "applied": False,
                "action": None,
                "summary": "No autocorrection needed.",
            }

            if validation["ok"] is not True:
                self._finalize_task_execution(
                    task_execution,
                    status="failed",
                    summary=f"Initial validation failed for {task.ticket_id}.",
                    error_message=validation.get("stderr") or validation.get("summary"),
                )
                autocorrection = self._attempt_autocorrect(
                    blueprint_id=blueprint_id,
                    task=task,
                    recipe=recipe,
                    workspace_root=workspace_root,
                    failed_execution=task_execution,
                    validation=validation,
                    guardrail_policy=guardrail_policy,
                )
                if autocorrection["applied"] is True:
                    final_task_execution = self.tracking_service.create_task_execution(
                        blueprint_id=blueprint_id,
                        delivery_task_id=task.id,
                        agent_run_id=agent_run.id,
                        status="in_progress",
                        attempt_number=2,
                        summary=f"Retry after autocorrection: {autocorrection['action']}",
                    )
                    validation = self._validate_recipe(
                        recipe=recipe,
                        workspace_root=workspace_root,
                    )
                    attempts.append(
                        {
                            "attempt_number": 2,
                            "validation": validation,
                            "autocorrection_applied": True,
                        }
                    )

            summary = (
                f"{recipe.summary} Wrote {len(written_paths)} file(s) "
                f"for {task.ticket_id}."
            )
            self._complete_records(
                agent_run=agent_run,
                task_execution=final_task_execution,
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
                "task_execution_id": final_task_execution.id,
                "files": [str(path.relative_to(workspace_root)) for path in written_paths],
                "artifacts": artifact_payloads,
                "validation": validation,
                "autocorrection": autocorrection,
                "attempts": attempts,
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
                "autocorrection": {
                    "applied": False,
                    "action": None,
                    "summary": str(exc),
                },
                "attempts": [],
            }

    def _run_review_stage(
        self,
        *,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        workspace_root: Path,
        execution_payloads: list[dict[str, Any]],
    ) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        for execution in execution_payloads:
            if execution["status"] != "done":
                findings.append(
                    {
                        "ticket_id": execution["ticket_id"],
                        "severity": "high",
                        "summary": execution["validation"].get("summary", "Validation failed."),
                    }
                )

        verdict = "approved" if not findings else "changes_requested"
        approved = verdict == "approved"
        review_run = self.tracking_service.create_agent_run(
            blueprint_id=blueprint_id,
            agent_name="semi_automatic_review",
            agent_role="review",
            provider="mission_control",
            model="heuristic_review",
            status="running",
            input_summary=f"Reviewing {len(execution_payloads)} delivery execution(s).",
            runtime_name="semi_automatic",
        )
        self.tracking_service.create_handoff(
            blueprint_id=blueprint_id,
            from_agent="semi_automatic_delivery",
            to_agent="semi_automatic_review",
            status="completed",
            reason="Execution completed; requesting review verdict.",
            context={
                "ticket_ids": [item["ticket_id"] for item in execution_payloads],
                "workspace_root": str(workspace_root),
            },
        )

        summary = (
            "Review approved the selected delivery items."
            if approved
            else f"Review found {len(findings)} blocking finding(s)."
        )
        payload = {
            "verdict": verdict,
            "approved": approved,
            "finding_count": len(findings),
            "findings": findings,
            "summary": summary,
            "agent_run_id": review_run.id,
        }
        self._finalize_agent_run(
            review_run,
            status="completed",
            output_summary=json.dumps(payload, ensure_ascii=False),
            error_message=None,
        )
        self.tracking_service.create_stage_event(
            blueprint_id=blueprint_id,
            stage_name="review",
            status="completed" if approved else "blocked",
            source=DELIVERY_SOURCE,
            summary=summary,
            metadata={
                "scrum_plan_id": plan.id,
                "verdict": verdict,
                "finding_count": len(findings),
                "workspace_root": str(workspace_root),
            },
        )
        self.blueprint_persistence_service.add_stage_feedback(
            blueprint_id=blueprint_id,
            stage_name="review",
            status=verdict,
            source=DELIVERY_SOURCE,
            feedback_text=json.dumps(payload, ensure_ascii=False),
        )
        return payload

    def _run_qa_gate(
        self,
        *,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        workspace_root: Path,
        execution_payloads: list[dict[str, Any]],
        review_result: dict[str, Any],
    ) -> dict[str, Any]:
        checks = [
            {
                "rule": "all_task_executions_done",
                "ok": all(item["status"] == "done" for item in execution_payloads),
            },
            {
                "rule": "all_validations_passed",
                "ok": all(item["validation"]["ok"] is True for item in execution_payloads),
            },
            {
                "rule": "review_approved",
                "ok": review_result["approved"] is True,
            },
            {
                "rule": "workspace_contains_generated_files",
                "ok": all(
                    (workspace_root / relative_path).exists()
                    for item in execution_payloads
                    for relative_path in item["files"]
                ),
            },
        ]

        passed = all(check["ok"] for check in checks)
        verdict = "passed" if passed else "failed"
        summary = "QA gate passed." if passed else "QA gate failed."
        qa_run = self.tracking_service.create_agent_run(
            blueprint_id=blueprint_id,
            agent_name="semi_automatic_qa",
            agent_role="qa",
            provider="mission_control",
            model="heuristic_qa_gate",
            status="running",
            input_summary=f"QA gate for scrum plan v{plan.version}.",
            runtime_name="semi_automatic",
        )
        self.tracking_service.create_handoff(
            blueprint_id=blueprint_id,
            from_agent="semi_automatic_review",
            to_agent="semi_automatic_qa",
            status="completed",
            reason="Review completed; requesting QA gate decision.",
            context={
                "review_verdict": review_result["verdict"],
                "workspace_root": str(workspace_root),
            },
        )

        payload = {
            "verdict": verdict,
            "passed": passed,
            "checks": checks,
            "summary": summary,
            "agent_run_id": qa_run.id,
        }
        self._finalize_agent_run(
            qa_run,
            status="completed",
            output_summary=json.dumps(payload, ensure_ascii=False),
            error_message=None,
        )
        self.tracking_service.create_stage_event(
            blueprint_id=blueprint_id,
            stage_name="qa_gate",
            status="completed" if passed else "failed",
            source=DELIVERY_SOURCE,
            summary=summary,
            metadata={
                "scrum_plan_id": plan.id,
                "verdict": verdict,
                "workspace_root": str(workspace_root),
                "checks": checks,
            },
        )
        self.blueprint_persistence_service.add_stage_feedback(
            blueprint_id=blueprint_id,
            stage_name="qa_gate",
            status=verdict,
            source=DELIVERY_SOURCE,
            feedback_text=json.dumps(payload, ensure_ascii=False),
        )
        return payload

    def _build_supporting_artifacts(
        self,
        *,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        workspace_root: Path,
        execution_payloads: list[dict[str, Any]],
        review_result: dict[str, Any],
        qa_gate_result: dict[str, Any],
        guardrail_policy: ArchitectureGuardrailPolicy,
    ) -> dict[str, Any]:
        artifact_run = self.tracking_service.create_agent_run(
            blueprint_id=blueprint_id,
            agent_name="artifact_builder",
            agent_role="documentation",
            provider="mission_control",
            model="artifact_builder",
            status="running",
            input_summary=f"Building delivery artifacts for scrum plan v{plan.version}.",
            runtime_name="semi_automatic",
        )
        self.tracking_service.create_handoff(
            blueprint_id=blueprint_id,
            from_agent="semi_automatic_qa",
            to_agent="artifact_builder",
            status="completed",
            reason="QA gate completed; build execution evidence artifacts.",
            context={
                "qa_verdict": qa_gate_result["verdict"],
                "workspace_root": str(workspace_root),
            },
        )

        test_evidence_payload = {
            "plan_id": plan.id,
            "plan_version": plan.version,
            "executions": [
                {
                    "ticket_id": item["ticket_id"],
                    "status": item["status"],
                    "validation": item["validation"],
                    "attempts": item.get("attempts", []),
                    "autocorrection": item.get("autocorrection", {}),
                }
                for item in execution_payloads
            ],
        }
        summary_markdown = self._render_delivery_summary_markdown(
            plan=plan,
            execution_payloads=execution_payloads,
            review_result=review_result,
            qa_gate_result=qa_gate_result,
        )
        artifact_specs = [
            (
                ".mission_control/reports/test_evidence.json",
                json.dumps(test_evidence_payload, ensure_ascii=False, indent=2) + "\n",
                "evidence",
            ),
            (
                ".mission_control/reports/review_report.json",
                json.dumps(review_result, ensure_ascii=False, indent=2) + "\n",
                "report",
            ),
            (
                ".mission_control/reports/qa_gate.json",
                json.dumps(qa_gate_result, ensure_ascii=False, indent=2) + "\n",
                "report",
            ),
            (
                ".mission_control/reports/delivery_summary.md",
                summary_markdown,
                "report",
            ),
        ]
        artifacts = [
            self._write_supporting_artifact(
                blueprint_id=blueprint_id,
                agent_run_id=artifact_run.id,
                workspace_root=workspace_root,
                relative_path=relative_path,
                content=content,
                artifact_type=artifact_type,
                guardrail_policy=guardrail_policy,
                metadata={
                    "scrum_plan_id": plan.id,
                    "generated_by": "artifact_builder",
                },
            )
            for relative_path, content, artifact_type in artifact_specs
        ]
        self._finalize_agent_run(
            artifact_run,
            status="completed",
            output_summary=(
                f"Built {len(artifacts)} supporting artifact(s) for scrum plan v{plan.version}."
            ),
            error_message=None,
        )
        return {
            "agent_run_id": artifact_run.id,
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
        }

    def _create_release_candidate(
        self,
        *,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        workspace_root: Path,
        generated_artifacts: list[dict[str, Any]],
        supporting_artifacts: list[dict[str, Any]],
        qa_gate_result: dict[str, Any],
        auto_merge_current_branch: bool,
        guardrail_policy: ArchitectureGuardrailPolicy,
    ) -> dict[str, Any]:
        release_run = self.tracking_service.create_agent_run(
            blueprint_id=blueprint_id,
            agent_name="release_candidate_builder",
            agent_role="release",
            provider="mission_control",
            model="local_git_release",
            status="running",
            input_summary=f"Creating release candidate for scrum plan v{plan.version}.",
            runtime_name="semi_automatic",
        )
        self.tracking_service.create_handoff(
            blueprint_id=blueprint_id,
            from_agent="artifact_builder",
            to_agent="release_candidate_builder",
            status="completed",
            reason="Artifacts completed; create release candidate.",
            context={
                "artifact_count": len(generated_artifacts) + len(supporting_artifacts),
                "workspace_root": str(workspace_root),
            },
        )

        release_payload: dict[str, Any] = {
            "status": "blocked",
            "ok": False,
            "workspace_root": str(workspace_root),
            "git_repository": False,
            "branch_name": None,
            "commit_sha": None,
            "merged": False,
        }
        stage_status = "blocked"
        summary = "Release candidate blocked because QA gate did not pass."

        try:
            if qa_gate_result["passed"] is True:
                release_payload = self._create_release_manifest_for_workspace(
                    workspace_root=workspace_root,
                    blueprint_id=blueprint_id,
                    plan=plan,
                    generated_artifacts=generated_artifacts,
                    supporting_artifacts=supporting_artifacts,
                    auto_merge_current_branch=auto_merge_current_branch,
                    guardrail_policy=guardrail_policy,
                )
                stage_status = "completed" if release_payload["ok"] is True else "failed"
                summary = (
                    "Release candidate created and merged to the current branch."
                    if release_payload["merged"] is True
                    else "Release candidate created successfully."
                )
            release_artifact = self._write_supporting_artifact(
                blueprint_id=blueprint_id,
                agent_run_id=release_run.id,
                workspace_root=workspace_root,
                relative_path=".mission_control/releases/release_candidate.json",
                content=json.dumps(release_payload, ensure_ascii=False, indent=2) + "\n",
                artifact_type="release",
                guardrail_policy=guardrail_policy,
                metadata={"scrum_plan_id": plan.id},
            )
            release_payload["artifact"] = release_artifact
            self._finalize_agent_run(
                release_run,
                status="completed" if release_payload["ok"] is True or stage_status == "blocked" else "failed",
                output_summary=json.dumps(release_payload, ensure_ascii=False),
                error_message=None if release_payload["ok"] is True or stage_status == "blocked" else summary,
            )
        except Exception as exc:
            release_payload["status"] = "failed"
            release_payload["summary"] = str(exc)
            stage_status = "failed"
            summary = f"Release candidate failed: {exc}"
            self._finalize_agent_run(
                release_run,
                status="failed",
                output_summary=json.dumps(release_payload, ensure_ascii=False),
                error_message=str(exc),
            )

        self.tracking_service.create_stage_event(
            blueprint_id=blueprint_id,
            stage_name="release",
            status=stage_status,
            source=DELIVERY_SOURCE,
            summary=summary,
            metadata={
                "scrum_plan_id": plan.id,
                "release_payload": release_payload,
            },
        )
        self.blueprint_persistence_service.add_stage_feedback(
            blueprint_id=blueprint_id,
            stage_name="release",
            status=release_payload["status"],
            source=DELIVERY_SOURCE,
            feedback_text=json.dumps(release_payload, ensure_ascii=False),
        )
        return release_payload

    def _close_sprint_and_record_retro(
        self,
        *,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        workspace_root: Path,
        selected_sprint_cycles: list[SprintCycleRecord],
        execution_payloads: list[dict[str, Any]],
        review_result: dict[str, Any],
        qa_gate_result: dict[str, Any],
        release_result: dict[str, Any],
        guardrail_policy: ArchitectureGuardrailPolicy,
    ) -> dict[str, Any]:
        sprint_completed = qa_gate_result["passed"] is True and release_result["ok"] is True
        self._update_sprint_statuses(
            selected_sprint_cycles,
            status="completed" if sprint_completed else "blocked",
        )

        retro_run = self.tracking_service.create_agent_run(
            blueprint_id=blueprint_id,
            agent_name="retro_facilitator",
            agent_role="retrospective",
            provider="mission_control",
            model="heuristic_retro",
            status="running",
            input_summary=f"Build retrospective for scrum plan v{plan.version}.",
            runtime_name="semi_automatic",
        )
        self.tracking_service.create_handoff(
            blueprint_id=blueprint_id,
            from_agent="release_candidate_builder",
            to_agent="retro_facilitator",
            status="completed",
            reason="Release stage finished; capture sprint review and retrospective.",
            context={
                "release_status": release_result["status"],
                "workspace_root": str(workspace_root),
            },
        )

        closed_item_count = sum(1 for item in execution_payloads if item["status"] == "done")
        review_summary = (
            f"Sprint review: {closed_item_count}/{len(execution_payloads)} selected items completed. "
            f"Review={review_result['verdict']}, QA={qa_gate_result['verdict']}, Release={release_result['status']}."
        )
        retrospective_markdown = (
            "# Sprint Retrospective\n\n"
            f"- Resultado: {'exitoso' if sprint_completed else 'con hallazgos'}\n"
            f"- Tickets ejecutados: {closed_item_count}/{len(execution_payloads)}\n"
            f"- Review: {review_result['verdict']}\n"
            f"- QA Gate: {qa_gate_result['verdict']}\n"
            f"- Release: {release_result['status']}\n"
        )

        retro_artifact = self._write_supporting_artifact(
            blueprint_id=blueprint_id,
            agent_run_id=retro_run.id,
            workspace_root=workspace_root,
            relative_path=".mission_control/reports/retrospective.md",
            content=retrospective_markdown,
            artifact_type="report",
            guardrail_policy=guardrail_policy,
            metadata={"scrum_plan_id": plan.id},
        )
        retrospective_items = [
            self.blueprint_persistence_service.add_retrospective_item(
                blueprint_id=blueprint_id,
                category="win",
                summary=(
                    "Selected sprint items reached release candidate stage."
                    if sprint_completed
                    else "The sprint surfaced delivery gaps before merge."
                ),
                action_item="Expand recipe coverage and keep QA rules green.",
                owner="Jarvis-PM",
                status="closed" if sprint_completed else "open",
            ).to_dict(),
            self.blueprint_persistence_service.add_retrospective_item(
                blueprint_id=blueprint_id,
                category="improvement",
                summary="Keep adding deterministic delivery recipes and validation rules.",
                action_item="Implement broader workspace-aware generation for non-template tickets.",
                owner="Jarvis-PM",
                status="open",
            ).to_dict(),
        ]

        self.tracking_service.create_stage_event(
            blueprint_id=blueprint_id,
            stage_name="retrospective",
            status="completed",
            source=DELIVERY_SOURCE,
            summary=review_summary,
            metadata={
                "scrum_plan_id": plan.id,
                "selected_sprint_ids": [cycle.id for cycle in selected_sprint_cycles],
                "workspace_root": str(workspace_root),
            },
        )
        self.blueprint_persistence_service.add_stage_feedback(
            blueprint_id=blueprint_id,
            stage_name="review",
            status=review_result["verdict"],
            source=DELIVERY_SOURCE,
            feedback_text=review_summary,
        )
        self._finalize_agent_run(
            retro_run,
            status="completed",
            output_summary=review_summary,
            error_message=None,
        )
        return {
            "agent_run_id": retro_run.id,
            "artifact": retro_artifact,
            "item_count": len(retrospective_items),
            "items": retrospective_items,
            "sprint_closed": sprint_completed,
            "selected_sprint_ids": [cycle.id for cycle in selected_sprint_cycles],
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
        guardrail_policy: ArchitectureGuardrailPolicy,
    ) -> list[Path]:
        written_paths: list[Path] = []
        for file_spec in recipe.files:
            output_path = self._write_guardrailed_file(
                workspace_root=workspace_root,
                relative_path=file_spec.path,
                content=file_spec.content,
                guardrail_policy=guardrail_policy,
            )
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

    def _attempt_autocorrect(
        self,
        *,
        blueprint_id: int,
        task: DeliveryTaskRecord,
        recipe: DeliveryRecipe,
        workspace_root: Path,
        failed_execution: TaskExecutionRecord,
        validation: dict[str, Any],
        guardrail_policy: ArchitectureGuardrailPolicy,
    ) -> dict[str, Any]:
        if recipe.name == "terraform_s3_module" and shutil.which("terraform") is not None:
            completed = subprocess.run(
                ["terraform", "fmt"],
                cwd=workspace_root / "infra",
                capture_output=True,
                text=True,
                timeout=30,
            )
            applied = completed.returncode == 0
            action = "terraform fmt"
            summary = (
                "Applied terraform fmt before retry."
                if applied
                else f"terraform fmt failed: {completed.stderr.strip()}"
            )
        else:
            self._write_recipe_files(
                workspace_root=workspace_root,
                recipe=recipe,
                guardrail_policy=guardrail_policy,
            )
            applied = True
            action = "rewrite_recipe_files"
            summary = "Rewrote recipe files before retry."

        self.tracking_service.create_handoff(
            blueprint_id=blueprint_id,
            task_execution_id=failed_execution.id,
            from_agent="semi_automatic_delivery",
            to_agent="semi_automatic_delivery",
            status="completed" if applied else "rejected",
            reason="Autocorrection retry after failed validation.",
            context={
                "ticket_id": task.ticket_id,
                "recipe": recipe.name,
                "validation": validation,
                "action": action,
            },
        )
        return {
            "applied": applied,
            "action": action,
            "summary": summary,
        }

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
    def _resolve_selected_sprint_cycles(items: list[ScrumPlanItemRecord]) -> list[SprintCycleRecord]:
        seen_ids: set[int] = set()
        sprint_cycles: list[SprintCycleRecord] = []
        for item in items:
            if item.sprint_cycle is None or item.sprint_cycle.id in seen_ids:
                continue
            sprint_cycles.append(item.sprint_cycle)
            seen_ids.add(item.sprint_cycle.id)
        return sprint_cycles

    @staticmethod
    def _update_sprint_statuses(
        sprint_cycles: list[SprintCycleRecord],
        *,
        status: str,
    ) -> None:
        if not sprint_cycles:
            return
        for sprint_cycle in sprint_cycles:
            sprint_cycle.status = status
        db.session.commit()

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
    def _finalize_task_execution(
        task_execution: TaskExecutionRecord,
        *,
        status: str,
        summary: str,
        error_message: str | None,
    ) -> None:
        task_execution.status = status
        task_execution.summary = summary
        task_execution.error_message = error_message
        task_execution.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

    @staticmethod
    def _finalize_agent_run(
        agent_run: AgentRunRecord,
        *,
        status: str,
        output_summary: str | None,
        error_message: str | None,
    ) -> None:
        agent_run.status = status
        agent_run.output_summary = output_summary
        agent_run.error_message = error_message
        agent_run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

    @staticmethod
    def _write_guardrailed_file(
        *,
        workspace_root: Path,
        relative_path: str,
        content: str,
        guardrail_policy: ArchitectureGuardrailPolicy,
    ) -> Path:
        normalized_path = validate_relative_path(relative_path, guardrail_policy)
        output_path = (workspace_root / normalized_path).resolve()
        if output_path != workspace_root and workspace_root not in output_path.parents:
            raise ValueError(f"Path escapes workspace root: {relative_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def _write_supporting_artifact(
        self,
        *,
        blueprint_id: int,
        agent_run_id: int,
        workspace_root: Path,
        relative_path: str,
        content: str,
        artifact_type: str,
        guardrail_policy: ArchitectureGuardrailPolicy,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output_path = self._write_guardrailed_file(
            workspace_root=workspace_root,
            relative_path=relative_path,
            content=content,
            guardrail_policy=guardrail_policy,
        )
        artifact = self.tracking_service.create_artifact(
            blueprint_id=blueprint_id,
            agent_run_id=agent_run_id,
            name=output_path.name,
            artifact_type=artifact_type,
            uri=str(output_path),
            metadata=metadata or {},
        )
        return artifact.to_dict()

    @staticmethod
    def _render_delivery_summary_markdown(
        *,
        plan: ScrumPlanRecord,
        execution_payloads: list[dict[str, Any]],
        review_result: dict[str, Any],
        qa_gate_result: dict[str, Any],
    ) -> str:
        lines = [
            "# Delivery Summary",
            "",
            f"- Scrum plan: v{plan.version}",
            f"- Tickets ejecutados: {len(execution_payloads)}",
            f"- Review: {review_result['verdict']}",
            f"- QA Gate: {qa_gate_result['verdict']}",
            "",
            "## Tickets",
        ]
        for execution in execution_payloads:
            lines.append(
                f"- {execution['ticket_id']}: {execution['status']} ({execution['recipe']})"
            )
        return "\n".join(lines) + "\n"

    def _create_release_manifest_for_workspace(
        self,
        *,
        workspace_root: Path,
        blueprint_id: int,
        plan: ScrumPlanRecord,
        generated_artifacts: list[dict[str, Any]],
        supporting_artifacts: list[dict[str, Any]],
        auto_merge_current_branch: bool,
        guardrail_policy: ArchitectureGuardrailPolicy,
    ) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "status": "completed",
            "ok": True,
            "git_repository": False,
            "branch_name": None,
            "commit_sha": None,
            "merged": False,
            "selected_artifact_count": len(generated_artifacts) + len(supporting_artifacts),
        }
        if shutil.which("git") is None or not self._is_git_workspace(workspace_root):
            manifest["status"] = "workspace_manifest_created"
            manifest["summary"] = "Workspace is not a git repository; created local release manifest only."
            return manifest

        manifest["git_repository"] = True
        self._ensure_git_identity(workspace_root)
        original_branch = self._git_current_branch(workspace_root)
        branch_name = f"mission-control/blueprint-{blueprint_id}-plan-{plan.version}-rc"
        manifest["branch_name"] = branch_name

        add_paths = [
            *[artifact["uri"] for artifact in generated_artifacts],
            *[artifact["uri"] for artifact in supporting_artifacts],
        ]
        relative_add_paths = [str(Path(path).resolve().relative_to(workspace_root)) for path in add_paths]
        assert_allowed_paths(relative_add_paths, guardrail_policy)
        self._run_git(["checkout", "-B", branch_name], cwd=workspace_root)
        if relative_add_paths:
            self._run_git(["add", "--", *relative_add_paths], cwd=workspace_root)
        staged_files = self._git_output(["diff", "--cached", "--name-only"], cwd=workspace_root).splitlines()
        if staged_files:
            self._run_git(
                [
                    "commit",
                    "-m",
                    f"feat: release candidate for blueprint {blueprint_id} plan v{plan.version}",
                ],
                cwd=workspace_root,
            )
            manifest["commit_sha"] = self._git_output(["rev-parse", "HEAD"], cwd=workspace_root).strip()
        else:
            manifest["commit_sha"] = self._git_output(["rev-parse", "HEAD"], cwd=workspace_root).strip()

        if auto_merge_current_branch and original_branch:
            self._run_git(["checkout", original_branch], cwd=workspace_root)
            self._run_git(["merge", "--ff-only", branch_name], cwd=workspace_root)
            manifest["merged"] = True
            manifest["merge_target"] = original_branch
            manifest["merged_commit_sha"] = self._git_output(["rev-parse", "HEAD"], cwd=workspace_root).strip()
        elif original_branch:
            self._run_git(["checkout", original_branch], cwd=workspace_root)

        manifest["summary"] = (
            f"Release candidate created on {branch_name} and merged into {manifest.get('merge_target')}."
            if manifest["merged"] is True
            else f"Release candidate created on {branch_name}."
        )
        return manifest

    @staticmethod
    def _is_git_workspace(workspace_root: Path) -> bool:
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip() == "true"

    @staticmethod
    def _ensure_git_identity(workspace_root: Path) -> None:
        for key, value in (
            ("user.name", "Mission Control"),
            ("user.email", "mission-control@local"),
        ):
            completed = subprocess.run(
                ["git", "config", "--get", key],
                cwd=workspace_root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if completed.returncode != 0 or not completed.stdout.strip():
                subprocess.run(
                    ["git", "config", key, value],
                    cwd=workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True,
                )

    @staticmethod
    def _git_current_branch(workspace_root: Path) -> str | None:
        completed = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        branch = completed.stdout.strip()
        return branch or None

    @staticmethod
    def _git_output(command: list[str], *, cwd: Path) -> str:
        validate_unix_command("git " + " ".join(command))
        completed = subprocess.run(
            ["git", *command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return completed.stdout.strip()

    @staticmethod
    def _run_git(command: list[str], *, cwd: Path) -> None:
        validate_unix_command("git " + " ".join(command))
        subprocess.run(
            ["git", *command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

    @staticmethod
    def _normalize_text(raw_value: str) -> str:
        return " ".join(
            raw_value.lower().replace("_", " ").replace("-", " ").split()
        )
