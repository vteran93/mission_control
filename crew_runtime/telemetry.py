from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from database import (
    AgentRunRecord,
    DeliveryTaskRecord,
    HandoffRecord,
    LLMInvocationRecord,
    TaskExecutionRecord,
    db,
)

from .contracts import DispatchTask
from .crew_seeds import CrewSeed
from .model_registry import ModelProfile


@dataclass(frozen=True)
class RuntimeDispatchTrace:
    blueprint_id: int | None
    agent_run_id: int | None
    task_execution_id: int | None
    seed_name: str
    runtime_name: str
    target_agent: str


class RuntimeTelemetryRecorder:
    def start_dispatch(
        self,
        *,
        task: DispatchTask,
        seed: CrewSeed,
        profile: ModelProfile,
        runtime_name: str,
    ) -> RuntimeDispatchTrace:
        if task.project_blueprint_id is None:
            return RuntimeDispatchTrace(
                blueprint_id=None,
                agent_run_id=None,
                task_execution_id=None,
                seed_name=seed.name,
                runtime_name=runtime_name,
                target_agent=task.target_agent,
            )

        agent_run = AgentRunRecord(
            project_blueprint_id=task.project_blueprint_id,
            agent_name=self._humanize_agent_label(task.target_agent),
            agent_role=self._normalize_agent_role(task.target_agent),
            provider=profile.provider,
            model=profile.model,
            status="running",
            input_summary=task.content,
            runtime_name=runtime_name,
        )
        db.session.add(agent_run)
        db.session.flush()

        task_execution_id = None
        if task.delivery_task_id is not None and self._task_matches_blueprint(
            task.project_blueprint_id,
            task.delivery_task_id,
        ):
            task_execution = TaskExecutionRecord(
                project_blueprint_id=task.project_blueprint_id,
                delivery_task_id=task.delivery_task_id,
                agent_run_id=agent_run.id,
                status="in_progress",
                attempt_number=(task.retry_count or 0) + 1,
                summary=f"Queued through crew seed '{seed.name}'",
            )
            db.session.add(task_execution)
            db.session.flush()
            task_execution_id = task_execution.id

        db.session.commit()
        return RuntimeDispatchTrace(
            blueprint_id=task.project_blueprint_id,
            agent_run_id=agent_run.id,
            task_execution_id=task_execution_id,
            seed_name=seed.name,
            runtime_name=runtime_name,
            target_agent=task.target_agent,
        )

    def record_attempt(
        self,
        *,
        trace: RuntimeDispatchTrace,
        profile: ModelProfile,
        status: str,
        latency_ms: int,
        attempt_number: int,
        fallback_used: bool,
        error_message: str | None = None,
    ) -> None:
        if trace.blueprint_id is None:
            return

        db.session.add(
            LLMInvocationRecord(
                project_blueprint_id=trace.blueprint_id,
                agent_run_id=trace.agent_run_id,
                provider=profile.provider,
                model=profile.model,
                purpose=trace.seed_name,
                status=status,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                cost_usd=0.0,
                metadata_json={
                    "attempt_number": attempt_number,
                    "fallback_used": fallback_used,
                    "profile_name": profile.name,
                    "error_message": error_message,
                    "runtime_name": trace.runtime_name,
                },
            )
        )
        db.session.commit()

    def record_handoff(
        self,
        *,
        trace: RuntimeDispatchTrace,
        from_profile: ModelProfile,
        to_profile: ModelProfile,
        reason: str,
    ) -> None:
        if trace.blueprint_id is None or from_profile.name == to_profile.name:
            return

        db.session.add(
            HandoffRecord(
                project_blueprint_id=trace.blueprint_id,
                task_execution_id=trace.task_execution_id,
                from_agent=from_profile.name,
                to_agent=to_profile.name,
                status="completed",
                reason=reason,
                context_json={
                    "runtime_name": trace.runtime_name,
                    "seed_name": trace.seed_name,
                    "target_agent": trace.target_agent,
                },
            )
        )
        db.session.commit()

    def finish_dispatch(
        self,
        *,
        trace: RuntimeDispatchTrace,
        success: bool,
        profile: ModelProfile,
        output_summary: str | None,
        error_message: str | None,
    ) -> None:
        if trace.agent_run_id is None:
            return

        agent_run = db.session.get(AgentRunRecord, trace.agent_run_id)
        if agent_run is not None:
            agent_run.provider = profile.provider
            agent_run.model = profile.model
            agent_run.status = "completed" if success else "failed"
            agent_run.output_summary = output_summary
            agent_run.error_message = error_message
            agent_run.completed_at = self._utc_now()

        if trace.task_execution_id is not None:
            task_execution = db.session.get(TaskExecutionRecord, trace.task_execution_id)
            if task_execution is not None:
                task_execution.status = "done" if success else "failed"
                task_execution.summary = output_summary
                task_execution.error_message = error_message
                task_execution.completed_at = self._utc_now()

        db.session.commit()

    @staticmethod
    def _task_matches_blueprint(blueprint_id: int, delivery_task_id: int) -> bool:
        task = db.session.get(DeliveryTaskRecord, delivery_task_id)
        if task is None or task.epic is None:
            return False
        return task.epic.project_blueprint_id == blueprint_id

    @staticmethod
    def _normalize_agent_role(label: str) -> str:
        normalized = label.strip().lower()
        if normalized.startswith("jarvis-"):
            return normalized.split("jarvis-", 1)[1]
        return normalized

    @staticmethod
    def _humanize_agent_label(label: str) -> str:
        return "-".join(part.capitalize() for part in label.split("-"))

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
