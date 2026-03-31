from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from flask import current_app

from database import (
    AgentRunRecord,
    DeliveryTaskRecord,
    ProjectBlueprintRecord,
    ScrumPlanItemRecord,
    ScrumPlanRecord,
    SprintCycleRecord,
    SprintStageEventRecord,
    StageFeedbackRecord,
    db,
)


PRIORITY_RANK = {
    "p0": 0,
    "critical": 0,
    "high": 1,
    "p1": 1,
    "medium": 2,
    "p2": 2,
    "normal": 2,
    "low": 3,
    "p3": 3,
}
RISK_LEVEL_THRESHOLDS = (
    (75, "critical"),
    (55, "high"),
    (30, "medium"),
    (0, "low"),
)
READINESS_STATUSES = {"ready", "needs_clarification", "blocked"}
PLAN_ITEM_STATUSES = {"planned", "blocked"}
PLAN_STATUSES = {"active", "superseded", "draft"}
APPROVAL_STATUSES = {"draft", "review_required", "approved"}
ESTIMATE_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>sp|pts?|point|points|h|hs|hr|hrs|hora|horas|d|day|days|dia|dias)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PlannedTask:
    task: DeliveryTaskRecord
    sequence_index: int
    dependency_depth: int
    story_points: int
    capacity_cost: int
    risk_score: int
    risk_level: str
    readiness_status: str
    plan_status: str
    assignee_role: str
    sprint_order: int | None
    depends_on: list[str]
    blocked_by: list[str]
    definition_of_ready: list[dict[str, str]]
    definition_of_done: list[dict[str, str]]
    planning_notes: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class HeuristicPlanDraft:
    planning_start: datetime
    sprint_capacity: int
    sprint_length_days: int
    velocity_factor: float
    effective_capacity: int
    task_drafts: list[PlannedTask]
    ordering_warnings: list[str]
    blocked_ticket_ids: list[str]
    changed_ticket_ids: list[str]
    sprint_count: int
    total_story_points: int
    overall_risk_score: int
    confidence_score: float
    risk_level: str
    escalation_trigger: str
    summary: dict[str, object]


@dataclass(frozen=True)
class CrewWorkflowReview:
    stage_label: str
    target_agent: str
    crew_seed: str
    approval_status: str
    raw_output: str
    summary: str
    risks: list[str]
    actions: list[str]
    metadata: dict[str, object]


class AutonomousScrumPlannerService:
    """Generates and persists a versioned Scrum plan from a persisted blueprint."""

    def _get_blueprint_or_raise(self, blueprint_id: int) -> ProjectBlueprintRecord:
        blueprint = db.session.get(ProjectBlueprintRecord, blueprint_id)
        if blueprint is None:
            raise LookupError("Blueprint not found")
        return blueprint

    def list_plans(self, blueprint_id: int) -> list[ScrumPlanRecord]:
        self._get_blueprint_or_raise(blueprint_id)
        return (
            ScrumPlanRecord.query.filter_by(project_blueprint_id=blueprint_id)
            .order_by(ScrumPlanRecord.version.desc(), ScrumPlanRecord.created_at.desc())
            .all()
        )

    def get_plan(
        self,
        blueprint_id: int,
        *,
        plan_id: int | None = None,
        status: str | None = "active",
    ) -> ScrumPlanRecord:
        self._get_blueprint_or_raise(blueprint_id)
        query = ScrumPlanRecord.query.filter_by(project_blueprint_id=blueprint_id)
        if plan_id is not None:
            query = query.filter_by(id=plan_id)
        elif status and status != "latest":
            query = query.filter_by(status=status)
        plan = query.order_by(ScrumPlanRecord.version.desc(), ScrumPlanRecord.created_at.desc()).first()
        if plan is None:
            raise LookupError("Scrum plan not found for blueprint")
        return plan

    def generate_plan(
        self,
        *,
        blueprint_id: int,
        sprint_capacity: int = 16,
        sprint_length_days: int = 7,
        start_date: str | datetime | date | None = None,
        velocity_factor: float = 1.0,
        blocked_ticket_ids: list[str] | None = None,
        changed_ticket_ids: list[str] | None = None,
        planning_mode: str = "autonomous",
        replan_reason: str | None = None,
        source: str = "heuristic",
    ) -> ScrumPlanRecord:
        blueprint = self._get_blueprint_or_raise(blueprint_id)
        if sprint_capacity <= 0:
            raise ValueError("sprint_capacity must be positive")
        if sprint_length_days <= 0:
            raise ValueError("sprint_length_days must be positive")
        if velocity_factor <= 0:
            raise ValueError("velocity_factor must be positive")

        active_plan = self._get_active_plan(blueprint_id)
        next_version = (
            db.session.query(db.func.max(ScrumPlanRecord.version))
            .filter(ScrumPlanRecord.project_blueprint_id == blueprint_id)
            .scalar()
            or 0
        ) + 1

        draft = self._build_heuristic_plan_draft(
            blueprint=blueprint,
            sprint_capacity=sprint_capacity,
            sprint_length_days=sprint_length_days,
            start_date=start_date,
            velocity_factor=velocity_factor,
            blocked_ticket_ids=blocked_ticket_ids,
            changed_ticket_ids=changed_ticket_ids,
        )

        reviews: list[CrewWorkflowReview] = [
            self._run_mandatory_planning_review(
                blueprint=blueprint,
                plan_version=next_version,
                draft=draft,
                planning_mode=planning_mode,
                replan_reason=replan_reason,
            )
        ]
        if draft.escalation_trigger == "bedrock_review":
            reviews.append(
                self._run_senior_bedrock_review(
                    blueprint=blueprint,
                    plan_version=next_version,
                    draft=draft,
                    planning_mode=planning_mode,
                    replan_reason=replan_reason,
                    planning_review=reviews[0],
                )
            )

        approval_status = self._resolve_final_approval_status(
            draft=draft,
            reviews=reviews,
        )
        lifecycle_status = "active" if approval_status == "approved" else "draft"

        if lifecycle_status == "active" and active_plan is not None:
            active_plan.status = "superseded"

        plan_record = ScrumPlanRecord(
            project_blueprint_id=blueprint_id,
            version=next_version,
            status=lifecycle_status,
            approval_status=approval_status,
            planning_mode=planning_mode,
            source=source,
            sprint_capacity=sprint_capacity,
            sprint_length_days=sprint_length_days,
            velocity_factor=velocity_factor,
            start_date=draft.planning_start,
            end_date=None,
            confidence_score=draft.confidence_score,
            risk_score=draft.overall_risk_score,
            risk_level=draft.risk_level,
            escalation_trigger=draft.escalation_trigger,
            replan_reason=replan_reason,
            summary_json={
                **draft.summary,
                "approval_status": approval_status,
                "execution_ready": approval_status == "approved",
                "planning_crew": self._serialize_review(reviews[0]),
                "senior_review": self._serialize_review(reviews[1]) if len(reviews) > 1 else None,
            },
        )
        db.session.add(plan_record)
        db.session.flush()

        sprint_records = self._persist_sprint_cycles(
            blueprint_id=blueprint_id,
            plan_record=plan_record,
            plan_version=next_version,
            draft=draft,
        )
        self._persist_plan_items(
            blueprint_id=blueprint_id,
            plan_record=plan_record,
            draft=draft,
            sprint_records=sprint_records,
        )
        self._persist_ceremonies(
            blueprint_id=blueprint_id,
            plan_id=plan_record.id,
            plan_version=next_version,
            sprint_count=draft.sprint_count,
            overall_risk_score=draft.overall_risk_score,
            confidence_score=draft.confidence_score,
            approval_status=approval_status,
            escalation_trigger=draft.escalation_trigger,
            reviews=reviews,
            replan_reason=replan_reason,
        )

        db.session.commit()
        return plan_record

    def approve_plan(
        self,
        blueprint_id: int,
        *,
        plan_id: int,
        source: str = "manual",
        feedback_text: str | None = None,
    ) -> ScrumPlanRecord:
        plan = self.get_plan(blueprint_id, plan_id=plan_id, status=None)
        active_plan = self._get_active_plan(blueprint_id)
        if active_plan is not None and active_plan.id != plan.id:
            active_plan.status = "superseded"

        plan.status = "active"
        plan.approval_status = "approved"
        summary = dict(plan.summary_json or {})
        summary["approval_status"] = "approved"
        summary["execution_ready"] = True
        summary["approved_via"] = source
        if feedback_text:
            summary["approval_feedback"] = feedback_text
        plan.summary_json = summary

        for event in self._plan_events(plan):
            if event.stage_name == "planning":
                event.status = "completed"
                event.summary = (
                    f"Scrum plan v{plan.version} aprobado para ejecucion autonoma."
                )

        self._ensure_operational_ceremonies(plan)
        db.session.add(
            StageFeedbackRecord(
                project_blueprint_id=blueprint_id,
                stage_name="planning",
                status="approved",
                source=source,
                feedback_text=(
                    f"[ScrumPlan v{plan.version}][approval] Approval=approved "
                    f"Source={source} Feedback={feedback_text or 'n/a'}"
                ),
            )
        )
        db.session.commit()
        return plan

    def serialize_plan(self, plan: ScrumPlanRecord) -> dict[str, object]:
        items = sorted(
            plan.items,
            key=lambda item: (
                item.sprint_order if item.sprint_order is not None else 9999,
                item.sequence_index,
            ),
        )
        sprint_cycles = sorted(
            plan.sprint_cycles,
            key=lambda item: item.metadata_json.get("sprint_order", 9999) if item.metadata_json else 9999,
        )
        ceremonies = [
            event.to_dict()
            for event in sorted(
                plan.blueprint.sprint_stage_events if plan.blueprint else [],
                key=lambda item: item.created_at.isoformat() if item.created_at else "",
            )
            if isinstance(event.metadata_json, dict) and event.metadata_json.get("scrum_plan_id") == plan.id
        ]
        planning_feedback = [
            feedback.to_dict()
            for feedback in sorted(
                plan.blueprint.stage_feedback if plan.blueprint else [],
                key=lambda item: item.created_at.isoformat() if item.created_at else "",
            )
            if feedback.feedback_text.startswith(f"[ScrumPlan v{plan.version}]")
        ]
        return {
            **plan.to_dict(),
            "items": [item.to_dict() for item in items],
            "sprint_cycles": [item.to_dict() for item in sprint_cycles],
            "ceremonies": ceremonies,
            "planning_feedback": planning_feedback,
        }

    def get_plan_context(self, blueprint_id: int, *, plan_id: int | None = None) -> dict[str, object]:
        plan = self.get_plan(blueprint_id, plan_id=plan_id)
        payload = self.serialize_plan(plan)
        sprint_view = self.build_sprint_view(blueprint_id, plan_id=plan.id, status=None)
        return {
            "plan": {
                key: payload[key]
                for key in (
                    "id",
                    "version",
                    "status",
                    "approval_status",
                    "planning_mode",
                    "source",
                    "confidence_score",
                    "risk_score",
                    "risk_level",
                    "escalation_trigger",
                    "summary",
                )
            },
            "sprint_cycles": payload["sprint_cycles"],
            "items": payload["items"],
            "ceremonies": payload["ceremonies"],
            "sprint_view": sprint_view,
        }

    def build_sprint_view(
        self,
        blueprint_id: int,
        *,
        plan_id: int | None = None,
        status: str | None = "latest",
    ) -> dict[str, object]:
        resolved_status = status if plan_id is None else None
        plan = self.get_plan(blueprint_id, plan_id=plan_id, status=resolved_status)
        items = sorted(
            list(plan.items),
            key=lambda item: (
                item.sprint_order if item.sprint_order is not None else 9999,
                item.sequence_index,
            ),
        )
        sprint_cycles = sorted(
            list(plan.sprint_cycles),
            key=lambda item: item.metadata_json.get("sprint_order", 9999) if item.metadata_json else 9999,
        )
        blocked_items = [item for item in items if item.plan_status == "blocked"]

        sprint_payloads: list[dict[str, object]] = []
        total_capacity = 0
        total_consumed_capacity = 0
        for sprint_cycle in sprint_cycles:
            sprint_order = sprint_cycle.metadata_json.get("sprint_order") if sprint_cycle.metadata_json else None
            sprint_items = [
                item
                for item in items
                if item.sprint_cycle_id == sprint_cycle.id
                or (item.sprint_cycle_id is None and sprint_order is not None and item.sprint_order == sprint_order)
            ]
            consumed_capacity = sum(item.capacity_cost for item in sprint_items if item.plan_status == "planned")
            total_consumed_capacity += consumed_capacity
            total_capacity += sprint_cycle.capacity or 0
            blocked_ticket_ids = [item.delivery_task.ticket_id for item in sprint_items if item.plan_status == "blocked"]
            ready_count = sum(1 for item in sprint_items if item.readiness_status == "ready")
            needs_clarification_count = sum(
                1 for item in sprint_items if item.readiness_status == "needs_clarification"
            )
            readiness_status = self._resolve_sprint_readiness_status(
                approval_status=plan.approval_status,
                sprint_items=sprint_items,
            )
            sprint_payloads.append(
                {
                    "sprint_cycle_id": sprint_cycle.id,
                    "sprint_order": sprint_order,
                    "name": sprint_cycle.name,
                    "goal": sprint_cycle.goal,
                    "status": sprint_cycle.status,
                    "capacity": sprint_cycle.capacity,
                    "consumed_capacity": consumed_capacity,
                    "remaining_capacity": max(0, (sprint_cycle.capacity or 0) - consumed_capacity),
                    "ticket_count": len(sprint_items),
                    "ticket_ids": [item.delivery_task.ticket_id for item in sprint_items if item.delivery_task],
                    "blocked_ticket_ids": blocked_ticket_ids,
                    "blocked_ticket_count": len(blocked_ticket_ids),
                    "ready_ticket_count": ready_count,
                    "needs_clarification_ticket_count": needs_clarification_count,
                    "readiness_status": readiness_status,
                    "execution_ready": plan.approval_status == "approved" and readiness_status == "ready",
                    "risk_score": sprint_cycle.metadata_json.get("risk_score", 0) if sprint_cycle.metadata_json else 0,
                    "risk_level": sprint_cycle.metadata_json.get("risk_level", "low") if sprint_cycle.metadata_json else "low",
                    "assignee_roles": sprint_cycle.metadata_json.get("assignee_roles", {}) if sprint_cycle.metadata_json else {},
                    "start_date": sprint_cycle.start_date.isoformat() if sprint_cycle.start_date else None,
                    "end_date": sprint_cycle.end_date.isoformat() if sprint_cycle.end_date else None,
                }
            )

        overall_readiness = plan.approval_status
        if plan.approval_status == "approved":
            if blocked_items:
                overall_readiness = "blocked"
            elif any(item.readiness_status == "needs_clarification" for item in items):
                overall_readiness = "needs_clarification"
            else:
                overall_readiness = "ready"

        return {
            "blueprint_id": blueprint_id,
            "plan": {
                "id": plan.id,
                "version": plan.version,
                "status": plan.status,
                "approval_status": plan.approval_status,
                "planning_mode": plan.planning_mode,
                "escalation_trigger": plan.escalation_trigger,
                "risk_level": plan.risk_level,
                "risk_score": plan.risk_score,
                "confidence_score": plan.confidence_score,
                "execution_ready": plan.approval_status == "approved",
            },
            "summary": {
                "sprint_count": len(sprint_cycles),
                "total_capacity": total_capacity,
                "total_consumed_capacity": total_consumed_capacity,
                "total_remaining_capacity": max(0, total_capacity - total_consumed_capacity),
                "blocked_ticket_count": len(blocked_items),
                "blocked_ticket_ids": [item.delivery_task.ticket_id for item in blocked_items if item.delivery_task],
                "ready_ticket_count": sum(1 for item in items if item.readiness_status == "ready"),
                "needs_clarification_ticket_count": sum(
                    1 for item in items if item.readiness_status == "needs_clarification"
                ),
                "overall_readiness": overall_readiness,
            },
            "blocked_backlog": [item.to_dict() for item in blocked_items],
            "sprints": sprint_payloads,
        }

    def _build_heuristic_plan_draft(
        self,
        *,
        blueprint: ProjectBlueprintRecord,
        sprint_capacity: int,
        sprint_length_days: int,
        start_date: str | datetime | date | None,
        velocity_factor: float,
        blocked_ticket_ids: list[str] | None,
        changed_ticket_ids: list[str] | None,
    ) -> HeuristicPlanDraft:
        planning_start = self._coerce_datetime(start_date) or self._default_start_date()
        blocked_ids = {item.strip() for item in blocked_ticket_ids or [] if item and item.strip()}
        changed_ids = {item.strip() for item in changed_ticket_ids or [] if item and item.strip()}
        effective_capacity = max(1, int(round(sprint_capacity * velocity_factor)))

        tasks = self._load_ordered_tasks(blueprint)
        ordered_tasks, ordering_warnings = self._order_tasks(tasks)
        dependency_depths = self._compute_dependency_depths(tasks)
        task_map = {task.ticket_id: task for task in tasks}

        capacity_by_sprint: dict[int, int] = Counter()
        assigned_sprint_by_ticket: dict[str, int | None] = {}
        task_drafts: list[PlannedTask] = []

        for sequence_index, task in enumerate(ordered_tasks, start=1):
            story_points = self._estimate_story_points(task.estimate)
            depends_on = list(task.dependencies_json or [])
            missing_dependencies = [dependency for dependency in depends_on if dependency not in task_map]

            blocked_by: list[str] = []
            if task.ticket_id in blocked_ids:
                blocked_by.append("Ticket marcado como bloqueado para esta corrida de planning.")
            if missing_dependencies:
                blocked_by.append(
                    f"Dependencias no encontradas en el blueprint: {', '.join(missing_dependencies)}."
                )

            resolved_dependency_sprints: list[int] = []
            for dependency in depends_on:
                dependency_sprint = assigned_sprint_by_ticket.get(dependency)
                if dependency in task_map and dependency_sprint is None:
                    blocked_by.append(f"Depende de {dependency}, que no esta listo para planificarse.")
                elif dependency_sprint is not None:
                    resolved_dependency_sprints.append(dependency_sprint)

            readiness_status = self._determine_readiness(task, blocked_by)
            plan_status = "blocked" if blocked_by else "planned"
            sprint_order = None
            if plan_status == "planned":
                sprint_order = max(resolved_dependency_sprints, default=1)
                while (
                    capacity_by_sprint[sprint_order] + story_points > effective_capacity
                    and capacity_by_sprint[sprint_order] > 0
                ):
                    sprint_order += 1
                capacity_by_sprint[sprint_order] += story_points
                if story_points > effective_capacity:
                    blocked_by.append(
                        f"La estimacion ({story_points} pts) excede la capacidad efectiva del sprint ({effective_capacity})."
                    )
            assigned_sprint_by_ticket[task.ticket_id] = sprint_order

            risk_score = self._score_task_risk(
                task,
                blocked_by=blocked_by,
                changed=task.ticket_id in changed_ids,
                blueprint_issue_count=len(blueprint.issues_json or []),
            )
            risk_level = self._risk_level(risk_score)
            assignee_role = self._assign_role(task)
            definition_of_ready = self._build_definition_of_ready(task, blocked_by)
            definition_of_done = self._build_definition_of_done(task)
            planning_notes = self._build_planning_notes(
                task=task,
                readiness_status=readiness_status,
                assignee_role=assignee_role,
                sprint_order=sprint_order,
                changed=task.ticket_id in changed_ids,
                effective_capacity=effective_capacity,
            )

            task_drafts.append(
                PlannedTask(
                    task=task,
                    sequence_index=sequence_index,
                    dependency_depth=dependency_depths.get(task.ticket_id, 0),
                    story_points=story_points,
                    capacity_cost=story_points,
                    risk_score=risk_score,
                    risk_level=risk_level,
                    readiness_status=readiness_status,
                    plan_status=plan_status,
                    assignee_role=assignee_role,
                    sprint_order=sprint_order,
                    depends_on=depends_on,
                    blocked_by=blocked_by,
                    definition_of_ready=definition_of_ready,
                    definition_of_done=definition_of_done,
                    planning_notes=planning_notes,
                    metadata={
                        "priority_rank": self._priority_rank(task.priority),
                        "ticket_type": task.ticket_type,
                        "changed_scope": task.ticket_id in changed_ids,
                    },
                )
            )

        sprint_count = max((draft.sprint_order or 0 for draft in task_drafts), default=0)
        total_story_points = sum(draft.story_points for draft in task_drafts if draft.plan_status == "planned")
        overall_risk_score = self._average_score(draft.risk_score for draft in task_drafts)
        confidence_score = self._compute_confidence(
            task_drafts,
            blueprint_issue_count=len(blueprint.issues_json or []),
        )
        escalation_trigger = self._resolve_escalation_trigger(
            confidence_score=confidence_score,
            overall_risk_score=overall_risk_score,
            blocked_ticket_count=sum(1 for draft in task_drafts if draft.plan_status == "blocked"),
            changed_ticket_count=len(changed_ids),
        )

        return HeuristicPlanDraft(
            planning_start=planning_start,
            sprint_capacity=sprint_capacity,
            sprint_length_days=sprint_length_days,
            velocity_factor=velocity_factor,
            effective_capacity=effective_capacity,
            task_drafts=task_drafts,
            ordering_warnings=ordering_warnings,
            blocked_ticket_ids=sorted(
                draft.task.ticket_id for draft in task_drafts if draft.plan_status == "blocked"
            ),
            changed_ticket_ids=sorted(changed_ids),
            sprint_count=sprint_count,
            total_story_points=total_story_points,
            overall_risk_score=overall_risk_score,
            confidence_score=confidence_score,
            risk_level=self._risk_level(overall_risk_score),
            escalation_trigger=escalation_trigger,
            summary={
                "sprints_planned": sprint_count,
                "effective_capacity": effective_capacity,
                "total_story_points": total_story_points,
                "blocked_ticket_ids": sorted(
                    draft.task.ticket_id for draft in task_drafts if draft.plan_status == "blocked"
                ),
                "changed_ticket_ids": sorted(changed_ids),
                "ordering_warnings": ordering_warnings,
                "ready_ticket_count": sum(1 for draft in task_drafts if draft.readiness_status == "ready"),
                "needs_clarification_ticket_count": sum(
                    1 for draft in task_drafts if draft.readiness_status == "needs_clarification"
                ),
            },
        )

    def _persist_sprint_cycles(
        self,
        *,
        blueprint_id: int,
        plan_record: ScrumPlanRecord,
        plan_version: int,
        draft: HeuristicPlanDraft,
    ) -> dict[int, SprintCycleRecord]:
        sprint_records: dict[int, SprintCycleRecord] = {}
        last_sprint_end = draft.planning_start
        for sprint_order in range(1, draft.sprint_count + 1):
            sprint_tasks = [item for item in draft.task_drafts if item.sprint_order == sprint_order]
            sprint_start = draft.planning_start + timedelta(days=(sprint_order - 1) * plan_record.sprint_length_days)
            sprint_end = sprint_start + timedelta(days=plan_record.sprint_length_days)
            last_sprint_end = max(last_sprint_end, sprint_end)
            sprint_risk = self._average_score(item.risk_score for item in sprint_tasks)

            sprint_record = SprintCycleRecord(
                project_blueprint_id=blueprint_id,
                scrum_plan_id=plan_record.id,
                name=f"Sprint {sprint_order}",
                goal=self._build_sprint_goal(sprint_tasks),
                capacity=draft.effective_capacity,
                status="planned",
                start_date=sprint_start,
                end_date=sprint_end,
                metadata_json={
                    "scrum_plan_id": plan_record.id,
                    "scrum_plan_version": plan_version,
                    "sprint_order": sprint_order,
                    "story_points_planned": sum(item.story_points for item in sprint_tasks),
                    "risk_score": sprint_risk,
                    "risk_level": self._risk_level(sprint_risk),
                    "ticket_ids": [item.task.ticket_id for item in sprint_tasks],
                    "assignee_roles": dict(Counter(item.assignee_role for item in sprint_tasks)),
                },
            )
            db.session.add(sprint_record)
            db.session.flush()
            sprint_records[sprint_order] = sprint_record

        plan_record.end_date = last_sprint_end if sprint_records else draft.planning_start
        return sprint_records

    def _persist_plan_items(
        self,
        *,
        blueprint_id: int,
        plan_record: ScrumPlanRecord,
        draft: HeuristicPlanDraft,
        sprint_records: dict[int, SprintCycleRecord],
    ) -> None:
        for item in draft.task_drafts:
            sprint_cycle = sprint_records.get(item.sprint_order) if item.sprint_order is not None else None
            db.session.add(
                ScrumPlanItemRecord(
                    scrum_plan_id=plan_record.id,
                    project_blueprint_id=blueprint_id,
                    delivery_task_id=item.task.id,
                    sprint_cycle_id=sprint_cycle.id if sprint_cycle else None,
                    plan_status=item.plan_status,
                    readiness_status=item.readiness_status,
                    assignee_role=item.assignee_role,
                    sprint_order=item.sprint_order,
                    sequence_index=item.sequence_index,
                    dependency_depth=item.dependency_depth,
                    story_points=item.story_points,
                    capacity_cost=item.capacity_cost,
                    risk_score=item.risk_score,
                    risk_level=item.risk_level,
                    depends_on_json=item.depends_on,
                    blocked_by_json=item.blocked_by,
                    definition_of_ready_json=item.definition_of_ready,
                    definition_of_done_json=item.definition_of_done,
                    planning_notes=item.planning_notes,
                    metadata_json=item.metadata,
                )
            )

    def _run_mandatory_planning_review(
        self,
        *,
        blueprint: ProjectBlueprintRecord,
        plan_version: int,
        draft: HeuristicPlanDraft,
        planning_mode: str,
        replan_reason: str | None,
    ) -> CrewWorkflowReview:
        prompt = self._build_planning_prompt(
            blueprint=blueprint,
            plan_version=plan_version,
            draft=draft,
            planning_mode=planning_mode,
            replan_reason=replan_reason,
        )
        default_approval_status = "review_required" if draft.escalation_trigger == "bedrock_review" else "approved"
        return self._dispatch_review_task(
            blueprint_id=blueprint.id,
            target_agent="jarvis-pm",
            crew_seed="scrum_planning",
            stage_label="planning_crew",
            message_content=prompt,
            priority="high",
            default_approval_status=default_approval_status,
        )

    def _run_senior_bedrock_review(
        self,
        *,
        blueprint: ProjectBlueprintRecord,
        plan_version: int,
        draft: HeuristicPlanDraft,
        planning_mode: str,
        replan_reason: str | None,
        planning_review: CrewWorkflowReview,
    ) -> CrewWorkflowReview:
        runtime, _ = self._require_runtime()
        target_agent, crew_seed = self._resolve_senior_review_target(runtime)
        prompt = self._build_senior_review_prompt(
            blueprint=blueprint,
            plan_version=plan_version,
            draft=draft,
            planning_mode=planning_mode,
            replan_reason=replan_reason,
            planning_review=planning_review,
            target_agent=target_agent,
        )
        review = self._dispatch_review_task(
            blueprint_id=blueprint.id,
            target_agent=target_agent,
            crew_seed=crew_seed,
            stage_label="senior_bedrock_review",
            message_content=prompt,
            priority="urgent",
            default_approval_status="review_required",
        )
        if review.metadata.get("provider") != "bedrock":
            raise RuntimeError(
                "The 'bedrock_review' escalation trigger requires a Bedrock planner or reviewer profile"
            )
        return review

    def _dispatch_review_task(
        self,
        *,
        blueprint_id: int,
        target_agent: str,
        crew_seed: str,
        stage_label: str,
        message_content: str,
        priority: str,
        default_approval_status: str,
    ) -> CrewWorkflowReview:
        runtime, dispatcher = self._require_runtime()
        _, queue_entry = dispatcher.create_message_and_enqueue(
            target_agent=target_agent,
            message_content=message_content,
            from_agent="Mission Control Planner",
            priority=priority,
            project_blueprint_id=blueprint_id,
            crew_seed=crew_seed,
        )
        results = runtime.process_pending(queue_entry_id=queue_entry.id, limit=1)
        if not results:
            raise RuntimeError(f"{stage_label} could not be dispatched through the CrewAI runtime")

        result = results[0]
        if not result.get("success"):
            raise RuntimeError(result.get("detail") or f"{stage_label} failed to complete")

        runtime_metadata = dict(result.get("runtime_metadata") or {})
        agent_run = None
        agent_run_id = runtime_metadata.get("agent_run_id")
        if agent_run_id is not None:
            agent_run = db.session.get(AgentRunRecord, agent_run_id)
        raw_output = ""
        if agent_run is not None and agent_run.output_summary:
            raw_output = agent_run.output_summary.strip()
        if not raw_output:
            raw_output = str(result.get("detail") or "").strip()

        parsed_review = self._parse_review_output(
            raw_output,
            default_approval_status=default_approval_status,
        )
        return CrewWorkflowReview(
            stage_label=stage_label,
            target_agent=target_agent,
            crew_seed=crew_seed,
            approval_status=parsed_review["approval_status"],
            raw_output=raw_output,
            summary=parsed_review["summary"],
            risks=parsed_review["risks"],
            actions=parsed_review["actions"],
            metadata={
                **runtime_metadata,
                "provider": result.get("provider"),
                "model": result.get("model"),
                "profile_name": result.get("external_ref"),
                "runtime_name": result.get("runtime_name"),
                "attempts": result.get("attempts"),
                "fallback_used": result.get("fallback_used"),
            },
        )

    def _persist_ceremonies(
        self,
        *,
        blueprint_id: int,
        plan_id: int,
        plan_version: int,
        sprint_count: int,
        overall_risk_score: int,
        confidence_score: float,
        approval_status: str,
        escalation_trigger: str,
        reviews: list[CrewWorkflowReview],
        replan_reason: str | None,
    ) -> None:
        plan_metadata = {
            "scrum_plan_id": plan_id,
            "scrum_plan_version": plan_version,
            "approval_status": approval_status,
            "escalation_trigger": escalation_trigger,
        }
        planning_status = "completed" if approval_status == "approved" else "blocked"
        planning_summary = (
            f"Scrum Planning Crew ejecutado para el plan v{plan_version} "
            f"con aprobacion={approval_status}, trigger={escalation_trigger}, riesgo={overall_risk_score}."
        )
        events = [
            SprintStageEventRecord(
                project_blueprint_id=blueprint_id,
                stage_name="planning",
                status=planning_status,
                source="scrum_planning_crew",
                summary=planning_summary,
                metadata_json={**plan_metadata, "replan_reason": replan_reason},
            )
        ]
        if approval_status == "approved":
            events.extend(
                [
                    SprintStageEventRecord(
                        project_blueprint_id=blueprint_id,
                        stage_name="daily_summary",
                        status="scheduled",
                        source="autonomous_scrum_planner",
                        summary=f"Se programaron daily summaries para {sprint_count} sprints planificados.",
                        metadata_json=plan_metadata,
                    ),
                    SprintStageEventRecord(
                        project_blueprint_id=blueprint_id,
                        stage_name="review",
                        status="scheduled",
                        source="autonomous_scrum_planner",
                        summary="Sprint review programada al cierre de cada sprint.",
                        metadata_json=plan_metadata,
                    ),
                    SprintStageEventRecord(
                        project_blueprint_id=blueprint_id,
                        stage_name="retrospective",
                        status="scheduled",
                        source="autonomous_scrum_planner",
                        summary="Retrospective programada para capturar mejoras del loop agentic.",
                        metadata_json=plan_metadata,
                    ),
                ]
            )
        else:
            events.append(
                SprintStageEventRecord(
                    project_blueprint_id=blueprint_id,
                    stage_name="review",
                    status="scheduled",
                    source="autonomous_scrum_planner",
                    summary="Se requiere revision/aprobacion antes de operar el sprint autonomamente.",
                    metadata_json=plan_metadata,
                )
            )

        db.session.add_all(events)
        db.session.add(
            StageFeedbackRecord(
                project_blueprint_id=blueprint_id,
                stage_name="planning",
                status="generated",
                source="autonomous_scrum_planner",
                feedback_text=(
                    f"[ScrumPlan v{plan_version}][summary] "
                    f"Confidence={confidence_score} Risk={overall_risk_score} "
                    f"Approval={approval_status} Trigger={escalation_trigger} "
                    f"ReplanReason={replan_reason or 'n/a'}"
                ),
            )
        )
        for review in reviews:
            db.session.add(
                StageFeedbackRecord(
                    project_blueprint_id=blueprint_id,
                    stage_name="planning",
                    status="generated",
                    source=review.stage_label,
                    feedback_text=(
                        f"[ScrumPlan v{plan_version}][{review.stage_label}] "
                        f"Approval={review.approval_status} Agent={review.target_agent} "
                        f"Seed={review.crew_seed} Summary={review.summary or 'n/a'} "
                        f"Raw={review.raw_output or 'n/a'}"
                    ),
                )
            )

    def _build_planning_prompt(
        self,
        *,
        blueprint: ProjectBlueprintRecord,
        plan_version: int,
        draft: HeuristicPlanDraft,
        planning_mode: str,
        replan_reason: str | None,
    ) -> str:
        payload = self._build_candidate_plan_payload(
            blueprint=blueprint,
            plan_version=plan_version,
            draft=draft,
            planning_mode=planning_mode,
            replan_reason=replan_reason,
        )
        return (
            "Actua como el Scrum Planning Crew obligatorio antes de persistir o aprobar este plan.\n"
            "Analiza el candidato heuristico y responde SOLO en JSON con este esquema:\n"
            '{\n'
            '  "approval_status": "approved|review_required|draft",\n'
            '  "summary": "resumen ejecutivo",\n'
            '  "risks": ["riesgo 1"],\n'
            '  "actions": ["accion 1"]\n'
            '}\n'
            "Usa review_required si el plan no esta listo para ejecucion autonoma.\n"
            f"Candidate plan:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _build_senior_review_prompt(
        self,
        *,
        blueprint: ProjectBlueprintRecord,
        plan_version: int,
        draft: HeuristicPlanDraft,
        planning_mode: str,
        replan_reason: str | None,
        planning_review: CrewWorkflowReview,
        target_agent: str,
    ) -> str:
        payload = self._build_candidate_plan_payload(
            blueprint=blueprint,
            plan_version=plan_version,
            draft=draft,
            planning_mode=planning_mode,
            replan_reason=replan_reason,
        )
        return (
            f"Actua como revisor senior Bedrock ({target_agent}) para un plan con trigger bedrock_review.\n"
            "Debes decidir si el plan puede aprobarse o si requiere revision adicional.\n"
            "Responde SOLO en JSON con este esquema:\n"
            '{\n'
            '  "approval_status": "approved|review_required|draft",\n'
            '  "summary": "veredicto corto",\n'
            '  "risks": ["riesgo 1"],\n'
            '  "actions": ["accion 1"]\n'
            '}\n'
            "Usa approved solo si el plan queda listo para ejecucion autonoma.\n"
            f"Planning crew verdict:\n{planning_review.raw_output}\n"
            f"Candidate plan:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _build_candidate_plan_payload(
        self,
        *,
        blueprint: ProjectBlueprintRecord,
        plan_version: int,
        draft: HeuristicPlanDraft,
        planning_mode: str,
        replan_reason: str | None,
    ) -> dict[str, object]:
        sprint_summaries = self._build_draft_sprint_summaries(draft)
        return {
            "blueprint_id": blueprint.id,
            "project_name": blueprint.project_name,
            "plan_version": plan_version,
            "planning_mode": planning_mode,
            "replan_reason": replan_reason,
            "confidence_score": draft.confidence_score,
            "risk_score": draft.overall_risk_score,
            "risk_level": draft.risk_level,
            "escalation_trigger": draft.escalation_trigger,
            "summary": draft.summary,
            "sprints": sprint_summaries,
            "blocked_tickets": [
                {
                    "ticket_id": item.task.ticket_id,
                    "title": item.task.title,
                    "blocked_by": item.blocked_by,
                    "risk_level": item.risk_level,
                }
                for item in draft.task_drafts
                if item.plan_status == "blocked"
            ],
            "items": [
                {
                    "ticket_id": item.task.ticket_id,
                    "title": item.task.title,
                    "sprint_order": item.sprint_order,
                    "plan_status": item.plan_status,
                    "readiness_status": item.readiness_status,
                    "assignee_role": item.assignee_role,
                    "story_points": item.story_points,
                    "risk_level": item.risk_level,
                    "depends_on": item.depends_on,
                    "blocked_by": item.blocked_by,
                    "planning_notes": item.planning_notes,
                }
                for item in draft.task_drafts
            ],
        }

    def _build_draft_sprint_summaries(self, draft: HeuristicPlanDraft) -> list[dict[str, object]]:
        sprint_summaries: list[dict[str, object]] = []
        for sprint_order in range(1, draft.sprint_count + 1):
            sprint_items = [item for item in draft.task_drafts if item.sprint_order == sprint_order]
            sprint_summaries.append(
                {
                    "sprint_order": sprint_order,
                    "capacity": draft.effective_capacity,
                    "consumed_capacity": sum(item.capacity_cost for item in sprint_items if item.plan_status == "planned"),
                    "ticket_ids": [item.task.ticket_id for item in sprint_items],
                    "ready_ticket_count": sum(1 for item in sprint_items if item.readiness_status == "ready"),
                    "needs_clarification_ticket_count": sum(
                        1 for item in sprint_items if item.readiness_status == "needs_clarification"
                    ),
                    "risk_score": self._average_score(item.risk_score for item in sprint_items),
                    "risk_level": self._risk_level(self._average_score(item.risk_score for item in sprint_items)),
                }
            )
        return sprint_summaries

    def _parse_review_output(
        self,
        raw_output: str,
        *,
        default_approval_status: str,
    ) -> dict[str, object]:
        approval_status = self._normalize_approval_status(default_approval_status, default="draft")
        summary = raw_output.strip()
        risks: list[str] = []
        actions: list[str] = []

        payload = self._extract_json_payload(raw_output)
        if payload is not None:
            approval_status = self._normalize_approval_status(
                payload.get("approval_status"),
                default=approval_status,
            )
            summary = str(
                payload.get("summary")
                or payload.get("executive_summary")
                or payload.get("verdict")
                or summary
            ).strip()
            risks = self._normalize_review_list(payload.get("risks") or payload.get("sprint_risks"))
            actions = self._normalize_review_list(payload.get("actions") or payload.get("follow_up_actions"))
        else:
            lowered = raw_output.lower()
            if "needs_work" in lowered or "needs work" in lowered:
                approval_status = "review_required"
            elif "review_required" in lowered or "requires review" in lowered or "revision" in lowered:
                approval_status = "review_required"
            elif "approved" in lowered and "not approved" not in lowered:
                approval_status = "approved"
            elif "draft" in lowered:
                approval_status = "draft"

        if not summary:
            summary = f"Approval={approval_status}"
        return {
            "approval_status": approval_status,
            "summary": summary[:600],
            "risks": risks[:10],
            "actions": actions[:10],
        }

    @staticmethod
    def _extract_json_payload(raw_output: str) -> dict[str, object] | None:
        candidate = raw_output.strip()
        if not candidate:
            return None
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            payload = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _normalize_review_list(raw_value) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            value = raw_value.strip()
            return [value] if value else []
        if not isinstance(raw_value, list):
            return []

        normalized: list[str] = []
        for item in raw_value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip())
            elif isinstance(item, dict):
                for key in ("item", "summary", "title", "action", "risk"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        normalized.append(value.strip())
                        break
        return normalized

    @staticmethod
    def _normalize_approval_status(raw_value, *, default: str) -> str:
        candidate = str(raw_value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if candidate == "needs_work":
            return "review_required"
        return candidate if candidate in APPROVAL_STATUSES else default

    def _resolve_final_approval_status(
        self,
        *,
        draft: HeuristicPlanDraft,
        reviews: list[CrewWorkflowReview],
    ) -> str:
        default_status = "review_required" if draft.escalation_trigger == "bedrock_review" else "approved"
        if not reviews:
            return default_status
        return self._normalize_approval_status(reviews[-1].approval_status, default=default_status)

    def _serialize_review(self, review: CrewWorkflowReview | None) -> dict[str, object] | None:
        if review is None:
            return None
        return {
            "stage_label": review.stage_label,
            "target_agent": review.target_agent,
            "crew_seed": review.crew_seed,
            "approval_status": review.approval_status,
            "summary": review.summary,
            "risks": review.risks,
            "actions": review.actions,
            "metadata": review.metadata,
            "raw_output": review.raw_output,
        }

    def _require_runtime(self):
        runtime = current_app.extensions.get("mission_control_runtime")
        dispatcher = current_app.extensions.get("queue_dispatcher")
        if runtime is None or dispatcher is None:
            raise RuntimeError("Mission Control runtime is not available in the current app context")
        if not runtime.dispatch_ready:
            raise RuntimeError("Scrum Planning Crew requires CrewAI runtime availability before persisting the plan")
        return runtime, dispatcher

    @staticmethod
    def _resolve_senior_review_target(runtime) -> tuple[str, str]:
        profiles = runtime.model_registry.profiles
        if "reviewer_bedrock" in profiles:
            return "jarvis-qa", "review"
        if "planner_bedrock" in profiles:
            return "jarvis-pm", "scrum_planning"
        raise RuntimeError(
            "The 'bedrock_review' trigger requires BEDROCK_REVIEWER_MODEL or BEDROCK_PLANNER_MODEL"
        )

    def _get_active_plan(self, blueprint_id: int) -> ScrumPlanRecord | None:
        return (
            ScrumPlanRecord.query.filter_by(project_blueprint_id=blueprint_id, status="active")
            .order_by(ScrumPlanRecord.version.desc())
            .first()
        )

    def _plan_events(self, plan: ScrumPlanRecord) -> list[SprintStageEventRecord]:
        blueprint = plan.blueprint or self._get_blueprint_or_raise(plan.project_blueprint_id)
        return [
            event
            for event in blueprint.sprint_stage_events
            if isinstance(event.metadata_json, dict) and event.metadata_json.get("scrum_plan_id") == plan.id
        ]

    def _ensure_operational_ceremonies(self, plan: ScrumPlanRecord) -> None:
        existing_stage_names = {event.stage_name for event in self._plan_events(plan)}
        plan_metadata = {
            "scrum_plan_id": plan.id,
            "scrum_plan_version": plan.version,
            "approval_status": plan.approval_status,
            "escalation_trigger": plan.escalation_trigger,
        }
        sprint_count = len(plan.sprint_cycles)
        if "daily_summary" not in existing_stage_names:
            db.session.add(
                SprintStageEventRecord(
                    project_blueprint_id=plan.project_blueprint_id,
                    stage_name="daily_summary",
                    status="scheduled",
                    source="autonomous_scrum_planner",
                    summary=f"Se programaron daily summaries para {sprint_count} sprints planificados.",
                    metadata_json=plan_metadata,
                )
            )
        if "review" not in existing_stage_names:
            db.session.add(
                SprintStageEventRecord(
                    project_blueprint_id=plan.project_blueprint_id,
                    stage_name="review",
                    status="scheduled",
                    source="autonomous_scrum_planner",
                    summary="Sprint review programada al cierre de cada sprint.",
                    metadata_json=plan_metadata,
                )
            )
        if "retrospective" not in existing_stage_names:
            db.session.add(
                SprintStageEventRecord(
                    project_blueprint_id=plan.project_blueprint_id,
                    stage_name="retrospective",
                    status="scheduled",
                    source="autonomous_scrum_planner",
                    summary="Retrospective programada para capturar mejoras del loop agentic.",
                    metadata_json=plan_metadata,
                )
            )

    def _resolve_sprint_readiness_status(
        self,
        *,
        approval_status: str,
        sprint_items: list[ScrumPlanItemRecord],
    ) -> str:
        if approval_status != "approved":
            return approval_status
        if any(item.plan_status == "blocked" or item.readiness_status == "blocked" for item in sprint_items):
            return "blocked"
        if any(item.readiness_status == "needs_clarification" for item in sprint_items):
            return "needs_clarification"
        return "ready"

    @staticmethod
    def _load_ordered_tasks(blueprint: ProjectBlueprintRecord) -> list[DeliveryTaskRecord]:
        tasks: list[DeliveryTaskRecord] = []
        for epic in sorted(blueprint.delivery_epics, key=lambda item: item.order_index):
            tasks.extend(sorted(epic.delivery_tasks, key=lambda item: item.order_index))
        return tasks

    def _order_tasks(self, tasks: list[DeliveryTaskRecord]) -> tuple[list[DeliveryTaskRecord], list[str]]:
        task_map = {task.ticket_id: task for task in tasks}
        adjacency: dict[str, list[str]] = {task.ticket_id: [] for task in tasks}
        incoming: dict[str, int] = {task.ticket_id: 0 for task in tasks}

        for task in tasks:
            for dependency in task.dependencies_json or []:
                if dependency in task_map:
                    adjacency[dependency].append(task.ticket_id)
                    incoming[task.ticket_id] += 1

        available = [task for task in tasks if incoming[task.ticket_id] == 0]
        ordered: list[DeliveryTaskRecord] = []
        warnings: list[str] = []

        while available:
            available.sort(key=self._task_sort_key)
            current = available.pop(0)
            ordered.append(current)
            for dependent_id in adjacency[current.ticket_id]:
                incoming[dependent_id] -= 1
                if incoming[dependent_id] == 0:
                    available.append(task_map[dependent_id])

        if len(ordered) != len(tasks):
            unresolved = [task_map[ticket_id] for ticket_id, count in incoming.items() if count > 0]
            unresolved.sort(key=self._task_sort_key)
            warnings.append(
                "Se detectaron dependencias ciclicas o irresueltas; los tickets restantes se ordenaron por prioridad."
            )
            ordered.extend(unresolved)

        return ordered, warnings

    def _compute_dependency_depths(self, tasks: list[DeliveryTaskRecord]) -> dict[str, int]:
        task_map = {task.ticket_id: task for task in tasks}
        memo: dict[str, int] = {}
        visiting: set[str] = set()

        def depth(ticket_id: str) -> int:
            if ticket_id in memo:
                return memo[ticket_id]
            if ticket_id in visiting:
                return 0
            visiting.add(ticket_id)
            task = task_map[ticket_id]
            known_dependencies = [dependency for dependency in task.dependencies_json or [] if dependency in task_map]
            value = 0
            if known_dependencies:
                value = 1 + max(depth(dependency) for dependency in known_dependencies)
            visiting.remove(ticket_id)
            memo[ticket_id] = value
            return value

        return {ticket_id: depth(ticket_id) for ticket_id in task_map}

    @staticmethod
    def _priority_rank(priority: str | None) -> int:
        normalized = (priority or "").strip().lower()
        return PRIORITY_RANK.get(normalized, 99)

    def _task_sort_key(self, task: DeliveryTaskRecord) -> tuple[int, int, int]:
        epic_order = task.epic.order_index if task.epic else 9999
        return (
            self._priority_rank(task.priority),
            epic_order,
            task.order_index,
        )

    def _determine_readiness(self, task: DeliveryTaskRecord, blocked_by: list[str]) -> str:
        if blocked_by:
            return "blocked"
        missing_context = (
            not (task.description or "").strip()
            or not (task.acceptance_criteria_json or [])
            or not (task.estimate or "").strip()
        )
        return "needs_clarification" if missing_context else "ready"

    @staticmethod
    def _estimate_story_points(estimate: str | None) -> int:
        if not estimate:
            return 3
        match = ESTIMATE_PATTERN.search(estimate)
        if match is None:
            return 3

        value = float(match.group("value"))
        unit = (match.group("unit") or "h").lower()
        if unit in {"sp", "pt", "pts", "point", "points"}:
            return max(1, int(round(value)))
        if unit in {"d", "day", "days", "dia", "dias"}:
            hours = value * 8
        else:
            hours = value

        if hours <= 2:
            return 1
        if hours <= 4:
            return 2
        if hours <= 8:
            return 3
        if hours <= 16:
            return 5
        if hours <= 24:
            return 8
        if hours <= 40:
            return 13
        return 21

    def _score_task_risk(
        self,
        task: DeliveryTaskRecord,
        *,
        blocked_by: list[str],
        changed: bool,
        blueprint_issue_count: int,
    ) -> int:
        score = 0
        if self._priority_rank(task.priority) <= 1:
            score += 12
        if not (task.estimate or "").strip():
            score += 15
        if not (task.acceptance_criteria_json or []):
            score += 18
        if not (task.description or "").strip():
            score += 12
        score += min(20, len(task.dependencies_json or []) * 6)
        score += min(25, len(blocked_by) * 12)
        if changed:
            score += 15
        if blueprint_issue_count:
            score += min(18, blueprint_issue_count * 6)
        if (task.ticket_type or "").strip().lower() in {"spike", "research", "discovery"}:
            score += 10
        return min(100, score)

    @staticmethod
    def _risk_level(score: int) -> str:
        for threshold, label in RISK_LEVEL_THRESHOLDS:
            if score >= threshold:
                return label
        return "low"

    @staticmethod
    def _assign_role(task: DeliveryTaskRecord) -> str:
        haystack = " ".join(
            filter(
                None,
                [
                    (task.ticket_type or "").lower(),
                    (task.title or "").lower(),
                    (task.description or "").lower(),
                ],
            )
        )
        if any(token in haystack for token in ("qa", "test", "review", "valid", "quality")):
            return "jarvis-qa"
        if any(token in haystack for token in ("plan", "roadmap", "spec", "analysis", "discovery")):
            return "jarvis-pm"
        return "jarvis-dev"

    def _build_definition_of_ready(
        self,
        task: DeliveryTaskRecord,
        blocked_by: list[str],
    ) -> list[dict[str, str]]:
        return [
            {
                "item": "Descripcion funcional del ticket disponible.",
                "status": "ready" if (task.description or "").strip() else "missing",
                "source": "roadmap",
            },
            {
                "item": "Estimacion registrada para reservar capacidad.",
                "status": "ready" if (task.estimate or "").strip() else "missing",
                "source": "roadmap",
            },
            {
                "item": "Criterios de aceptacion definidos para el sprint.",
                "status": "ready" if (task.acceptance_criteria_json or []) else "missing",
                "source": "roadmap",
            },
            {
                "item": "Dependencias resueltas para iniciar ejecucion.",
                "status": "blocked" if blocked_by else "ready",
                "source": "planner",
            },
        ]

    def _build_definition_of_done(self, task: DeliveryTaskRecord) -> list[dict[str, str]]:
        checklist = [
            {"item": criterion, "source": "roadmap"}
            for criterion in (task.acceptance_criteria_json or [])
        ]
        if not checklist:
            checklist.append(
                {
                    "item": "Resultado funcional validado contra el objetivo del ticket.",
                    "source": "planner",
                }
            )

        task_type = (task.ticket_type or "").strip().lower()
        checklist.extend(
            [
                {"item": "Pruebas automatizadas y smoke relevantes en verde.", "source": "planner"},
                {"item": "Artifacts y evidencia del trabajo persistidos en Mission Control.", "source": "planner"},
            ]
        )
        if any(token in task_type for token in ("docs", "documentation")):
            checklist.append({"item": "Documentacion Markdown actualizada.", "source": "planner"})
        if any(token in task_type for token in ("qa", "test", "review")):
            checklist.append({"item": "Evidencia QA adjunta con hallazgos o aprobacion.", "source": "planner"})
        if any(token in task_type for token in ("plan", "analysis")):
            checklist.append({"item": "Backlog y decisiones de planning persistidos.", "source": "planner"})
        return checklist

    @staticmethod
    def _build_planning_notes(
        *,
        task: DeliveryTaskRecord,
        readiness_status: str,
        assignee_role: str,
        sprint_order: int | None,
        changed: bool,
        effective_capacity: int,
    ) -> str:
        notes = [
            f"Asignar a {assignee_role}.",
            f"Readiness: {readiness_status}.",
            f"Capacidad efectiva de referencia: {effective_capacity} pts.",
        ]
        if sprint_order is not None:
            notes.append(f"Planificado para Sprint {sprint_order}.")
        if changed:
            notes.append("El ticket fue marcado con cambio de alcance en esta corrida.")
        if task.dependencies_json:
            notes.append(f"Depende de: {', '.join(task.dependencies_json)}.")
        return " ".join(notes)

    @staticmethod
    def _build_sprint_goal(sprint_tasks: list[PlannedTask]) -> str:
        if not sprint_tasks:
            return "Sprint reservado para estabilizacion y capacidad futura."
        top_tasks = ", ".join(item.task.title for item in sprint_tasks[:3])
        if len(sprint_tasks) <= 3:
            return f"Completar {top_tasks}."
        return f"Completar {top_tasks} y {len(sprint_tasks) - 3} tickets adicionales prioritarios."

    @staticmethod
    def _average_score(scores) -> int:
        values = [int(score) for score in scores]
        if not values:
            return 0
        return int(round(sum(values) / len(values)))

    @staticmethod
    def _compute_confidence(task_drafts: list[PlannedTask], *, blueprint_issue_count: int) -> float:
        if not task_drafts:
            return 0.0
        ready_ratio = sum(1 for draft in task_drafts if draft.readiness_status == "ready") / len(task_drafts)
        estimate_ratio = sum(1 for draft in task_drafts if draft.task.estimate) / len(task_drafts)
        acceptance_ratio = (
            sum(1 for draft in task_drafts if draft.task.acceptance_criteria_json) / len(task_drafts)
        )
        confidence = (0.4 * ready_ratio) + (0.3 * estimate_ratio) + (0.3 * acceptance_ratio)
        confidence -= min(0.2, blueprint_issue_count * 0.05)
        return round(max(0.0, min(1.0, confidence)), 4)

    @staticmethod
    def _resolve_escalation_trigger(
        *,
        confidence_score: float,
        overall_risk_score: int,
        blocked_ticket_count: int,
        changed_ticket_count: int,
    ) -> str:
        if blocked_ticket_count:
            return "blocked_dependency"
        if changed_ticket_count:
            return "scope_change"
        if overall_risk_score >= 70 or confidence_score < 0.65:
            return "bedrock_review"
        return "none"

    @staticmethod
    def _coerce_datetime(value: str | datetime | date | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        if isinstance(value, date):
            return datetime.combine(value, time(hour=9, minute=0))
        return datetime.fromisoformat(value).replace(tzinfo=None)

    @staticmethod
    def _default_start_date() -> datetime:
        now = datetime.now().replace(microsecond=0, second=0, minute=0)
        next_day = (now + timedelta(days=1)).date()
        return datetime.combine(next_day, time(hour=9, minute=0))
