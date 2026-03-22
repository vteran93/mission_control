from __future__ import annotations

import importlib.util
import sys
from time import perf_counter

from database import DaemonLog, Message, db

from .contracts import DispatchResult, DispatchTask
from .model_registry import ModelProfile, ModelRegistry


class CrewAIExecutor:
    name = "crewai"

    def __init__(self, model_registry: ModelRegistry):
        self.model_registry = model_registry
        try:
            self.available = importlib.util.find_spec("crewai") is not None
        except ValueError:
            self.available = "crewai" in sys.modules

    def dispatch(self, task: DispatchTask) -> DispatchResult:
        if not self.available:
            return DispatchResult(
                queue_id=task.queue_id,
                success=False,
                detail="CrewAI no esta instalado en el entorno actual",
                runtime_name=self.name,
            )

        profiles = self.model_registry.resolve_dispatch_profiles(
            task.target_agent,
            retry_count=task.retry_count,
        )
        failures: list[str] = []

        try:
            from crewai import Agent, Crew, LLM, Process, Task as CrewTask
        except Exception as exc:
            return DispatchResult(
                queue_id=task.queue_id,
                success=False,
                detail=f"CrewAI dispatch fallo al cargar el runtime: {exc}",
                runtime_name=self.name,
            )

        for attempt_number, profile in enumerate(profiles, start=1):
            seed = self._resolve_seed(task.target_agent)
            started_at = perf_counter()
            fallback_used = attempt_number > 1
            try:
                llm = LLM(**profile.to_llm_kwargs())
                agent = Agent(
                    role=seed["role"],
                    goal=seed["goal"],
                    backstory=seed["backstory"],
                    allow_delegation=False,
                    verbose=False,
                    llm=llm,
                )
                crew_task = CrewTask(
                    name=seed["crew_name"],
                    description=self._build_description(task, profile, seed),
                    expected_output=seed["expected_output"],
                    agent=agent,
                )
                crew = Crew(
                    name=seed["crew_name"],
                    agents=[agent],
                    tasks=[crew_task],
                    process=Process.hierarchical,
                    manager_llm=llm,
                    verbose=False,
                )

                crew_output = crew.kickoff()
                latency_ms = int((perf_counter() - started_at) * 1000)
                rendered_output = self._render_output(crew_output)
                self._persist_output(
                    task,
                    rendered_output,
                    profile,
                    latency_ms=latency_ms,
                    attempt_number=attempt_number,
                    fallback_used=fallback_used,
                )

                return DispatchResult(
                    queue_id=task.queue_id,
                    success=True,
                    detail=f"CrewAI ejecuto '{seed['crew_name']}' con el perfil '{profile.name}'",
                    runtime_name=self.name,
                    external_ref=profile.name,
                    provider=profile.provider,
                    model=profile.model,
                    latency_ms=latency_ms,
                    attempts=attempt_number,
                    fallback_used=fallback_used,
                )
            except Exception as exc:
                latency_ms = int((perf_counter() - started_at) * 1000)
                db.session.rollback()
                failures.append(f"{profile.name}: {exc}")
                self._persist_attempt_failure(
                    task,
                    profile,
                    latency_ms=latency_ms,
                    attempt_number=attempt_number,
                    exc=exc,
                    will_retry=attempt_number < len(profiles),
                )

        return DispatchResult(
            queue_id=task.queue_id,
            success=False,
            detail=f"CrewAI dispatch fallo: {' | '.join(failures)}",
            runtime_name=self.name,
            attempts=len(profiles),
            fallback_used=len(profiles) > 1,
        )

    def _resolve_seed(self, target_agent: str) -> dict[str, str]:
        label = target_agent.strip().lower()
        if label == "jarvis-pm":
            return {
                "crew_name": "planning",
                "role": "Product Manager",
                "goal": "Plan the next best action and unblock the requested work item.",
                "backstory": "You orchestrate engineering work with a pragmatic delivery mindset.",
                "expected_output": "A concise planning response with next action, risks, and decision.",
            }
        if label == "jarvis-qa":
            return {
                "crew_name": "review",
                "role": "QA Lead",
                "goal": "Review the requested change and identify quality risks or approvals.",
                "backstory": "You validate readiness and make the QA decision based on evidence.",
                "expected_output": "A QA verdict with findings, risks, and recommendation.",
            }
        return {
            "crew_name": "delivery",
            "role": "Senior Software Engineer",
            "goal": "Implement the requested change safely and report the result.",
            "backstory": "You execute software tasks with production discipline and clear outcomes.",
            "expected_output": "A concise implementation response with what changed, risks, and next step.",
        }

    def _build_description(
        self,
        task: DispatchTask,
        profile: ModelProfile,
        seed: dict[str, str],
    ) -> str:
        source_message = db.session.get(Message, task.message_id)
        task_id = source_message.task_id if source_message else None
        context_lines = [
            f"Queue ID: {task.queue_id}",
            f"Target agent: {task.target_agent}",
            f"From agent: {task.from_agent}",
            f"Priority: {task.priority}",
            f"Retry count: {task.retry_count}",
            f"Assigned crew seed: {seed['crew_name']}",
            f"Resolved model profile: {profile.name} ({profile.model})",
        ]
        if task_id is not None:
            context_lines.append(f"Task ID: {task_id}")
        context_lines.append("Instruction:")
        context_lines.append(task.content)
        return "\n".join(context_lines)

    def _render_output(self, crew_output) -> str:
        raw_output = getattr(crew_output, "raw", None)
        if isinstance(raw_output, str) and raw_output.strip():
            return raw_output.strip()
        return str(crew_output).strip()

    def _persist_output(
        self,
        task: DispatchTask,
        rendered_output: str,
        profile: ModelProfile,
        *,
        latency_ms: int,
        attempt_number: int,
        fallback_used: bool,
    ) -> None:
        source_message = db.session.get(Message, task.message_id)
        task_id = source_message.task_id if source_message else None
        db.session.add(
            Message(
                task_id=task_id,
                from_agent=self._humanize_agent_label(task.target_agent),
                content=rendered_output or "CrewAI completed without textual output.",
            )
        )
        db.session.add(
            DaemonLog(
                agent_name=self._normalize_daemon_agent_name(task.target_agent),
                level="INFO",
                message=(
                    f"CrewAI dispatch completado para queue_id={task.queue_id} con perfil "
                    f"{profile.name} ({profile.provider}/{profile.model}) en {latency_ms} ms"
                    f" [attempt={attempt_number}, fallback={fallback_used}]"
                ),
            )
        )
        db.session.commit()

    def _persist_attempt_failure(
        self,
        task: DispatchTask,
        profile: ModelProfile,
        *,
        latency_ms: int,
        attempt_number: int,
        exc: Exception,
        will_retry: bool,
    ) -> None:
        db.session.add(
            DaemonLog(
                agent_name=self._normalize_daemon_agent_name(task.target_agent),
                level="WARNING" if will_retry else "ERROR",
                message=(
                    f"CrewAI dispatch fallido para queue_id={task.queue_id} con perfil "
                    f"{profile.name} ({profile.provider}/{profile.model}) en {latency_ms} ms: {exc}"
                    f" [attempt={attempt_number}, fallback_retry={will_retry}]"
                ),
            )
        )
        db.session.commit()

    @staticmethod
    def _humanize_agent_label(label: str) -> str:
        return "-".join(part.capitalize() for part in label.split("-"))

    @staticmethod
    def _normalize_daemon_agent_name(label: str) -> str:
        normalized = label.strip().lower()
        if normalized.startswith("jarvis-"):
            return normalized.split("jarvis-", 1)[1]
        return normalized
