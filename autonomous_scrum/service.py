from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from database import (
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
        elif status:
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

        active_plan = (
            ScrumPlanRecord.query.filter_by(project_blueprint_id=blueprint_id, status="active")
            .order_by(ScrumPlanRecord.version.desc())
            .first()
        )
        next_version = (
            db.session.query(db.func.max(ScrumPlanRecord.version))
            .filter(ScrumPlanRecord.project_blueprint_id == blueprint_id)
            .scalar()
            or 0
        ) + 1

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

        sprint_records: dict[int, SprintCycleRecord] = {}
        last_sprint_end = planning_start
        sprint_count = max((draft.sprint_order or 0 for draft in task_drafts), default=0)
        total_story_points = sum(draft.story_points for draft in task_drafts if draft.plan_status == "planned")
        overall_risk_score = self._average_score(draft.risk_score for draft in task_drafts)
        confidence_score = self._compute_confidence(task_drafts, blueprint_issue_count=len(blueprint.issues_json or []))
        escalation_trigger = self._resolve_escalation_trigger(
            confidence_score=confidence_score,
            overall_risk_score=overall_risk_score,
            blocked_ticket_count=sum(1 for draft in task_drafts if draft.plan_status == "blocked"),
            changed_ticket_count=len(changed_ids),
        )

        if active_plan is not None:
            active_plan.status = "superseded"

        plan_record = ScrumPlanRecord(
            project_blueprint_id=blueprint_id,
            version=next_version,
            status="active",
            planning_mode=planning_mode,
            source=source,
            sprint_capacity=sprint_capacity,
            sprint_length_days=sprint_length_days,
            velocity_factor=velocity_factor,
            start_date=planning_start,
            end_date=None,
            confidence_score=confidence_score,
            risk_score=overall_risk_score,
            risk_level=self._risk_level(overall_risk_score),
            escalation_trigger=escalation_trigger,
            replan_reason=replan_reason,
            summary_json={
                "sprints_planned": sprint_count,
                "effective_capacity": effective_capacity,
                "total_story_points": total_story_points,
                "blocked_ticket_ids": sorted(draft.task.ticket_id for draft in task_drafts if draft.plan_status == "blocked"),
                "changed_ticket_ids": sorted(changed_ids),
                "ordering_warnings": ordering_warnings,
                "ready_ticket_count": sum(1 for draft in task_drafts if draft.readiness_status == "ready"),
                "needs_clarification_ticket_count": sum(
                    1 for draft in task_drafts if draft.readiness_status == "needs_clarification"
                ),
            },
        )
        db.session.add(plan_record)
        db.session.flush()

        for sprint_order in range(1, sprint_count + 1):
            sprint_tasks = [draft for draft in task_drafts if draft.sprint_order == sprint_order]
            sprint_start = planning_start + timedelta(days=(sprint_order - 1) * sprint_length_days)
            sprint_end = sprint_start + timedelta(days=sprint_length_days)
            last_sprint_end = max(last_sprint_end, sprint_end)
            sprint_risk = self._average_score(draft.risk_score for draft in sprint_tasks)

            sprint_record = SprintCycleRecord(
                project_blueprint_id=blueprint_id,
                scrum_plan_id=plan_record.id,
                name=f"Sprint {sprint_order}",
                goal=self._build_sprint_goal(sprint_tasks),
                capacity=effective_capacity,
                status="planned",
                start_date=sprint_start,
                end_date=sprint_end,
                metadata_json={
                    "scrum_plan_id": plan_record.id,
                    "scrum_plan_version": next_version,
                    "sprint_order": sprint_order,
                    "story_points_planned": sum(draft.story_points for draft in sprint_tasks),
                    "risk_score": sprint_risk,
                    "risk_level": self._risk_level(sprint_risk),
                    "ticket_ids": [draft.task.ticket_id for draft in sprint_tasks],
                    "assignee_roles": dict(Counter(draft.assignee_role for draft in sprint_tasks)),
                },
            )
            db.session.add(sprint_record)
            db.session.flush()
            sprint_records[sprint_order] = sprint_record

        plan_record.end_date = last_sprint_end if sprint_records else planning_start

        for draft in task_drafts:
            sprint_cycle = sprint_records.get(draft.sprint_order) if draft.sprint_order is not None else None
            db.session.add(
                ScrumPlanItemRecord(
                    scrum_plan_id=plan_record.id,
                    project_blueprint_id=blueprint_id,
                    delivery_task_id=draft.task.id,
                    sprint_cycle_id=sprint_cycle.id if sprint_cycle else None,
                    plan_status=draft.plan_status,
                    readiness_status=draft.readiness_status,
                    assignee_role=draft.assignee_role,
                    sprint_order=draft.sprint_order,
                    sequence_index=draft.sequence_index,
                    dependency_depth=draft.dependency_depth,
                    story_points=draft.story_points,
                    capacity_cost=draft.capacity_cost,
                    risk_score=draft.risk_score,
                    risk_level=draft.risk_level,
                    depends_on_json=draft.depends_on,
                    blocked_by_json=draft.blocked_by,
                    definition_of_ready_json=draft.definition_of_ready,
                    definition_of_done_json=draft.definition_of_done,
                    planning_notes=draft.planning_notes,
                    metadata_json=draft.metadata,
                )
            )

        self._persist_ceremonies(
            blueprint_id=blueprint_id,
            plan_id=plan_record.id,
            plan_version=next_version,
            sprint_count=sprint_count,
            overall_risk_score=overall_risk_score,
            confidence_score=confidence_score,
            replan_reason=replan_reason,
        )

        db.session.commit()
        return plan_record

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
        return {
            "plan": {
                key: payload[key]
                for key in (
                    "id",
                    "version",
                    "status",
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
        }

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
        top_tasks = ", ".join(draft.task.title for draft in sprint_tasks[:3])
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

    def _persist_ceremonies(
        self,
        *,
        blueprint_id: int,
        plan_id: int,
        plan_version: int,
        sprint_count: int,
        overall_risk_score: int,
        confidence_score: float,
        replan_reason: str | None,
    ) -> None:
        plan_metadata = {
            "scrum_plan_id": plan_id,
            "scrum_plan_version": plan_version,
        }
        events = [
            SprintStageEventRecord(
                project_blueprint_id=blueprint_id,
                stage_name="planning",
                status="completed",
                source="autonomous_scrum_planner",
                summary=(
                    f"Autonomous Scrum plan v{plan_version} generado con {sprint_count} sprints "
                    f"y riesgo {overall_risk_score}."
                ),
                metadata_json={**plan_metadata, "replan_reason": replan_reason},
            ),
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
        db.session.add_all(events)
        db.session.add(
            StageFeedbackRecord(
                project_blueprint_id=blueprint_id,
                stage_name="planning",
                status="generated",
                source="autonomous_scrum_planner",
                feedback_text=(
                    f"[ScrumPlan v{plan_version}] Confidence={confidence_score} "
                    f"Risk={overall_risk_score} ReplanReason={replan_reason or 'n/a'}"
                ),
            )
        )

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
