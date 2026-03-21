from __future__ import annotations

from collections import Counter, defaultdict

from database import (
    AgentRunRecord,
    ArtifactRecord,
    DeliveryTaskRecord,
    HandoffRecord,
    LLMInvocationRecord,
    ProjectBlueprintRecord,
    SprintCycleRecord,
    SprintStageEventRecord,
    StageFeedbackRecord,
    RetrospectiveItemRecord,
    TaskExecutionRecord,
    db,
)


VALID_SPRINT_CYCLE_STATUSES = {"planned", "active", "completed", "blocked", "cancelled"}
VALID_STAGE_NAMES = {"planning", "execution", "review", "qa_gate", "release", "retrospective"}
VALID_STAGE_STATUSES = {"scheduled", "in_progress", "completed", "blocked", "failed"}
VALID_AGENT_RUN_STATUSES = {"queued", "planning", "running", "blocked", "completed", "failed"}
VALID_TASK_EXECUTION_STATUSES = {"queued", "in_progress", "review", "done", "blocked", "failed"}
VALID_HANDOFF_STATUSES = {"requested", "accepted", "completed", "rejected"}
VALID_INVOCATION_STATUSES = {"completed", "failed", "cached", "retried"}


class DeliveryTrackingService:
    """Persistence and reporting for execution traces over a project blueprint."""

    def _get_blueprint_or_raise(self, blueprint_id: int) -> ProjectBlueprintRecord:
        blueprint = db.session.get(ProjectBlueprintRecord, blueprint_id)
        if blueprint is None:
            raise LookupError("Blueprint not found")
        return blueprint

    def _ensure_delivery_task_belongs_to_blueprint(self, blueprint_id: int, delivery_task_id: int) -> DeliveryTaskRecord:
        delivery_task = db.session.get(DeliveryTaskRecord, delivery_task_id)
        if delivery_task is None or delivery_task.epic is None or delivery_task.epic.project_blueprint_id != blueprint_id:
            raise LookupError("Delivery task not found for blueprint")
        return delivery_task

    def _ensure_agent_run_belongs_to_blueprint(self, blueprint_id: int, agent_run_id: int) -> AgentRunRecord:
        agent_run = db.session.get(AgentRunRecord, agent_run_id)
        if agent_run is None or agent_run.project_blueprint_id != blueprint_id:
            raise LookupError("Agent run not found for blueprint")
        return agent_run

    def _ensure_task_execution_belongs_to_blueprint(self, blueprint_id: int, task_execution_id: int) -> TaskExecutionRecord:
        task_execution = db.session.get(TaskExecutionRecord, task_execution_id)
        if task_execution is None or task_execution.project_blueprint_id != blueprint_id:
            raise LookupError("Task execution not found for blueprint")
        return task_execution

    def create_sprint_cycle(
        self,
        *,
        blueprint_id: int,
        name: str,
        goal: str | None = None,
        capacity: int | None = None,
        status: str = "planned",
        start_date=None,
        end_date=None,
        metadata: dict | None = None,
    ) -> SprintCycleRecord:
        self._get_blueprint_or_raise(blueprint_id)
        if status not in VALID_SPRINT_CYCLE_STATUSES:
            raise ValueError(f"Invalid sprint status: {status}")

        sprint_cycle = SprintCycleRecord(
            project_blueprint_id=blueprint_id,
            name=name,
            goal=goal or "",
            capacity=capacity,
            status=status,
            start_date=start_date,
            end_date=end_date,
            metadata_json=metadata or {},
        )
        db.session.add(sprint_cycle)
        db.session.commit()
        return sprint_cycle

    def create_stage_event(
        self,
        *,
        blueprint_id: int,
        stage_name: str,
        status: str,
        source: str,
        summary: str,
        metadata: dict | None = None,
    ) -> SprintStageEventRecord:
        self._get_blueprint_or_raise(blueprint_id)
        if stage_name not in VALID_STAGE_NAMES:
            raise ValueError(f"Invalid stage_name: {stage_name}")
        if status not in VALID_STAGE_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        event = SprintStageEventRecord(
            project_blueprint_id=blueprint_id,
            stage_name=stage_name,
            status=status,
            source=source,
            summary=summary,
            metadata_json=metadata or {},
        )
        db.session.add(event)
        db.session.commit()
        return event

    def create_agent_run(
        self,
        *,
        blueprint_id: int,
        agent_name: str,
        agent_role: str | None,
        provider: str | None,
        model: str | None,
        status: str,
        input_summary: str | None = None,
        output_summary: str | None = None,
        error_message: str | None = None,
        runtime_name: str | None = None,
        completed: bool = False,
    ) -> AgentRunRecord:
        self._get_blueprint_or_raise(blueprint_id)
        if status not in VALID_AGENT_RUN_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        run = AgentRunRecord(
            project_blueprint_id=blueprint_id,
            agent_name=agent_name,
            agent_role=agent_role,
            provider=provider,
            model=model,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            error_message=error_message,
            runtime_name=runtime_name,
        )
        if completed:
            run.completed_at = run.started_at
        db.session.add(run)
        db.session.commit()
        return run

    def create_task_execution(
        self,
        *,
        blueprint_id: int,
        delivery_task_id: int,
        agent_run_id: int | None,
        status: str,
        attempt_number: int,
        summary: str | None = None,
        error_message: str | None = None,
        completed: bool = False,
    ) -> TaskExecutionRecord:
        self._ensure_delivery_task_belongs_to_blueprint(blueprint_id, delivery_task_id)
        if agent_run_id is not None:
            self._ensure_agent_run_belongs_to_blueprint(blueprint_id, agent_run_id)
        if status not in VALID_TASK_EXECUTION_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        execution = TaskExecutionRecord(
            project_blueprint_id=blueprint_id,
            delivery_task_id=delivery_task_id,
            agent_run_id=agent_run_id,
            status=status,
            attempt_number=attempt_number,
            summary=summary,
            error_message=error_message,
        )
        if completed:
            execution.completed_at = execution.started_at
        db.session.add(execution)
        db.session.commit()
        return execution

    def create_artifact(
        self,
        *,
        blueprint_id: int,
        name: str,
        artifact_type: str,
        uri: str,
        agent_run_id: int | None = None,
        task_execution_id: int | None = None,
        document_id: int | None = None,
        metadata: dict | None = None,
    ) -> ArtifactRecord:
        self._get_blueprint_or_raise(blueprint_id)
        if agent_run_id is not None:
            self._ensure_agent_run_belongs_to_blueprint(blueprint_id, agent_run_id)
        if task_execution_id is not None:
            self._ensure_task_execution_belongs_to_blueprint(blueprint_id, task_execution_id)

        artifact = ArtifactRecord(
            project_blueprint_id=blueprint_id,
            agent_run_id=agent_run_id,
            task_execution_id=task_execution_id,
            document_id=document_id,
            name=name,
            artifact_type=artifact_type,
            uri=uri,
            metadata_json=metadata or {},
        )
        db.session.add(artifact)
        db.session.commit()
        return artifact

    def create_handoff(
        self,
        *,
        blueprint_id: int,
        from_agent: str,
        to_agent: str,
        status: str,
        reason: str,
        task_execution_id: int | None = None,
        context: dict | None = None,
    ) -> HandoffRecord:
        self._get_blueprint_or_raise(blueprint_id)
        if task_execution_id is not None:
            self._ensure_task_execution_belongs_to_blueprint(blueprint_id, task_execution_id)
        if status not in VALID_HANDOFF_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        handoff = HandoffRecord(
            project_blueprint_id=blueprint_id,
            task_execution_id=task_execution_id,
            from_agent=from_agent,
            to_agent=to_agent,
            status=status,
            reason=reason,
            context_json=context or {},
        )
        db.session.add(handoff)
        db.session.commit()
        return handoff

    def create_llm_invocation(
        self,
        *,
        blueprint_id: int,
        provider: str,
        model: str,
        purpose: str,
        status: str,
        agent_run_id: int | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int | None = None,
        cost_usd: float = 0.0,
        metadata: dict | None = None,
    ) -> LLMInvocationRecord:
        self._get_blueprint_or_raise(blueprint_id)
        if agent_run_id is not None:
            self._ensure_agent_run_belongs_to_blueprint(blueprint_id, agent_run_id)
        if status not in VALID_INVOCATION_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        invocation = LLMInvocationRecord(
            project_blueprint_id=blueprint_id,
            agent_run_id=agent_run_id,
            provider=provider,
            model=model,
            purpose=purpose,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            metadata_json=metadata or {},
        )
        db.session.add(invocation)
        db.session.commit()
        return invocation

    def build_timeline(self, blueprint_id: int) -> list[dict[str, object]]:
        blueprint = self._get_blueprint_or_raise(blueprint_id)
        timeline: list[dict[str, object]] = [
            {
                "event_type": "blueprint_created",
                "timestamp": blueprint.created_at.isoformat() if blueprint.created_at else None,
                "payload": blueprint.to_dict(),
            }
        ]

        def append_items(items, event_type: str):
            for item in items:
                timestamp = (
                    getattr(item, "created_at", None)
                    or getattr(item, "started_at", None)
                    or getattr(item, "completed_at", None)
                )
                timeline.append(
                    {
                        "event_type": event_type,
                        "timestamp": timestamp.isoformat() if timestamp else None,
                        "payload": item.to_dict(),
                    }
                )

        append_items(blueprint.sprint_stage_events, "sprint_stage_event")
        append_items(blueprint.stage_feedback, "stage_feedback")
        append_items(blueprint.agent_runs, "agent_run")
        append_items(blueprint.task_executions, "task_execution")
        append_items(blueprint.artifacts, "artifact")
        append_items(blueprint.handoffs, "handoff")
        append_items(blueprint.llm_invocations, "llm_invocation")
        append_items(blueprint.retrospective_items, "retrospective_item")
        append_items(blueprint.sprint_cycles, "sprint_cycle")

        timeline.sort(key=lambda item: item["timestamp"] or "")
        return timeline

    def build_report(self, blueprint_id: int) -> dict[str, object]:
        blueprint = self._get_blueprint_or_raise(blueprint_id)

        sprint_cycles = list(blueprint.sprint_cycles)
        agent_runs = list(blueprint.agent_runs)
        task_executions = list(blueprint.task_executions)
        stage_events = list(blueprint.sprint_stage_events)
        handoffs = list(blueprint.handoffs)
        llm_invocations = list(blueprint.llm_invocations)
        artifacts = list(blueprint.artifacts)

        sprint_cycle_status_counts = Counter(sprint.status for sprint in sprint_cycles)
        agent_run_status_counts = Counter(run.status for run in agent_runs)
        task_execution_status_counts = Counter(execution.status for execution in task_executions)
        stage_event_status_counts = Counter(event.status for event in stage_events)
        provider_breakdown = defaultdict(lambda: {"invocations": 0, "cost_usd": 0.0})
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_latency_ms = 0
        latency_samples = 0

        for invocation in llm_invocations:
            provider_breakdown[invocation.provider]["invocations"] += 1
            provider_breakdown[invocation.provider]["cost_usd"] += invocation.cost_usd or 0.0
            total_prompt_tokens += invocation.prompt_tokens or 0
            total_completion_tokens += invocation.completion_tokens or 0
            if invocation.latency_ms is not None:
                total_latency_ms += invocation.latency_ms
                latency_samples += 1

        retry_rate = 0.0
        if task_executions:
            retry_rate = round(
                sum(1 for execution in task_executions if execution.attempt_number > 1) / len(task_executions),
                4,
            )

        completed_task_count = sum(
            1 for execution in task_executions if execution.status in {"done", "completed"}
        )
        defect_leakage = sum(
            1 for execution in task_executions if execution.status in {"failed", "blocked"}
        )

        return {
            "blueprint_id": blueprint.id,
            "project_name": blueprint.project_name,
            "counts": {
                "requirements": len(blueprint.requirements),
                "epics": len(blueprint.delivery_epics),
                "delivery_tasks": sum(len(epic.delivery_tasks) for epic in blueprint.delivery_epics),
                "sprint_cycles": len(sprint_cycles),
                "stage_events": len(stage_events),
                "stage_feedback": len(blueprint.stage_feedback),
                "agent_runs": len(agent_runs),
                "task_executions": len(task_executions),
                "artifacts": len(artifacts),
                "handoffs": len(handoffs),
                "llm_invocations": len(llm_invocations),
                "retrospective_items": len(blueprint.retrospective_items),
            },
            "status_breakdown": {
                "sprint_cycles": dict(sprint_cycle_status_counts),
                "stage_events": dict(stage_event_status_counts),
                "agent_runs": dict(agent_run_status_counts),
                "task_executions": dict(task_execution_status_counts),
            },
            "llm": {
                "provider_breakdown": dict(provider_breakdown),
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_cost_usd": round(sum(item["cost_usd"] for item in provider_breakdown.values()), 6),
                "average_latency_ms": round(total_latency_ms / latency_samples, 2) if latency_samples else None,
            },
            "delivery_metrics": {
                "completed_task_count": completed_task_count,
                "retry_rate": retry_rate,
                "defect_leakage_estimate": defect_leakage,
                "throughput_estimate": completed_task_count,
            },
        }
