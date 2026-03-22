from __future__ import annotations

import importlib.util
import sys
from time import perf_counter

from database import DaemonLog, Message, db

from .contracts import DispatchResult, DispatchTask
from .crew_seeds import resolve_crew_seed
from .model_registry import ModelProfile, ModelRegistry
from .telemetry import RuntimeTelemetryRecorder
from .toolkit import RuntimeToolCatalog


class CrewAIExecutor:
    name = "crewai"

    def __init__(
        self,
        model_registry: ModelRegistry,
        tool_catalog: RuntimeToolCatalog | None = None,
    ):
        self.model_registry = model_registry
        self.tool_catalog = tool_catalog or RuntimeToolCatalog(model_registry.settings)
        self.telemetry_recorder = RuntimeTelemetryRecorder()
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
        seed = resolve_crew_seed(task.target_agent, task.crew_seed)
        tools = self.tool_catalog.build_tools_for_seed(seed)
        failures: list[str] = []
        trace = self.telemetry_recorder.start_dispatch(
            task=task,
            seed=seed,
            profile=profiles[0],
            runtime_name=self.name,
        )

        try:
            from crewai import Agent, Crew, LLM, Process, Task as CrewTask
        except Exception as exc:
            return DispatchResult(
                queue_id=task.queue_id,
                success=False,
                detail=f"CrewAI dispatch fallo al cargar el runtime: {exc}",
                runtime_name=self.name,
            )

        previous_profile: ModelProfile | None = None
        for attempt_number, profile in enumerate(profiles, start=1):
            started_at = perf_counter()
            fallback_used = attempt_number > 1
            try:
                if previous_profile is not None:
                    self.telemetry_recorder.record_handoff(
                        trace=trace,
                        from_profile=previous_profile,
                        to_profile=profile,
                        reason="Runtime fallback/escalation after previous provider failure",
                    )
                llm = LLM(**profile.to_llm_kwargs())
                agent = Agent(
                    role=seed.role,
                    goal=seed.goal,
                    backstory=seed.backstory,
                    allow_delegation=False,
                    verbose=False,
                    llm=llm,
                    tools=tools,
                )
                crew_task = CrewTask(
                    name=seed.name,
                    description=self._build_description(task, profile, seed),
                    expected_output=seed.expected_output,
                    agent=agent,
                )
                crew = Crew(
                    name=seed.name,
                    agents=[agent],
                    tasks=[crew_task],
                    process=Process.hierarchical,
                    manager_llm=llm,
                    verbose=False,
                )

                crew_output = crew.kickoff()
                latency_ms = int((perf_counter() - started_at) * 1000)
                rendered_output = self._render_output(crew_output)
                self.telemetry_recorder.record_attempt(
                    trace=trace,
                    profile=profile,
                    status="completed",
                    latency_ms=latency_ms,
                    attempt_number=attempt_number,
                    fallback_used=fallback_used,
                )
                self._persist_output(
                    task,
                    rendered_output,
                    profile,
                    seed_name=seed.name,
                    tool_count=len(tools),
                    latency_ms=latency_ms,
                    attempt_number=attempt_number,
                    fallback_used=fallback_used,
                )
                self.telemetry_recorder.finish_dispatch(
                    trace=trace,
                    success=True,
                    profile=profile,
                    output_summary=rendered_output,
                    error_message=None,
                )

                return DispatchResult(
                    queue_id=task.queue_id,
                    success=True,
                    detail=f"CrewAI ejecuto '{seed.name}' con el perfil '{profile.name}'",
                    runtime_name=self.name,
                    external_ref=profile.name,
                    provider=profile.provider,
                    model=profile.model,
                    latency_ms=latency_ms,
                    attempts=attempt_number,
                    fallback_used=fallback_used,
                    runtime_metadata={
                        "crew_seed": seed.name,
                        "tool_names": [getattr(tool, "name", str(tool)) for tool in tools],
                        "tool_count": len(tools),
                        "profile_name": profile.name,
                        "blueprint_id": task.project_blueprint_id,
                        "delivery_task_id": task.delivery_task_id,
                        "agent_run_id": trace.agent_run_id,
                        "task_execution_id": trace.task_execution_id,
                    },
                )
            except Exception as exc:
                latency_ms = int((perf_counter() - started_at) * 1000)
                db.session.rollback()
                failures.append(f"{profile.name}: {exc}")
                self.telemetry_recorder.record_attempt(
                    trace=trace,
                    profile=profile,
                    status="failed",
                    latency_ms=latency_ms,
                    attempt_number=attempt_number,
                    fallback_used=fallback_used,
                    error_message=str(exc),
                )
                self._persist_attempt_failure(
                    task,
                    profile,
                    latency_ms=latency_ms,
                    attempt_number=attempt_number,
                    exc=exc,
                    will_retry=attempt_number < len(profiles),
                )
                previous_profile = profile

        final_profile = profiles[-1]
        self.telemetry_recorder.finish_dispatch(
            trace=trace,
            success=False,
            profile=final_profile,
            output_summary=None,
            error_message=" | ".join(failures),
        )
        return DispatchResult(
            queue_id=task.queue_id,
            success=False,
            detail=f"CrewAI dispatch fallo: {' | '.join(failures)}",
            runtime_name=self.name,
            attempts=len(profiles),
            fallback_used=len(profiles) > 1,
            runtime_metadata={
                "crew_seed": seed.name,
                "tool_names": [getattr(tool, "name", str(tool)) for tool in tools],
                "tool_count": len(tools),
                "profile_name": final_profile.name,
                "blueprint_id": task.project_blueprint_id,
                "delivery_task_id": task.delivery_task_id,
                "agent_run_id": trace.agent_run_id,
                "task_execution_id": trace.task_execution_id,
            },
        )

    def _build_description(
        self,
        task: DispatchTask,
        profile: ModelProfile,
        seed,
    ) -> str:
        source_message = db.session.get(Message, task.message_id)
        task_id = source_message.task_id if source_message else None
        context_lines = [
            f"Queue ID: {task.queue_id}",
            f"Target agent: {task.target_agent}",
            f"From agent: {task.from_agent}",
            f"Priority: {task.priority}",
            f"Retry count: {task.retry_count}",
            f"Assigned crew seed: {seed.name}",
            f"Resolved model profile: {profile.name} ({profile.model})",
            f"Available tools: {', '.join(tool['name'] if isinstance(tool, dict) else getattr(tool, 'name', str(tool)) for tool in self.tool_catalog.describe_for_seed(seed))}",
        ]
        if task_id is not None:
            context_lines.append(f"Task ID: {task_id}")
        if task.project_blueprint_id is not None:
            context_lines.append(f"Project Blueprint ID: {task.project_blueprint_id}")
        if task.delivery_task_id is not None:
            context_lines.append(f"Delivery Task ID: {task.delivery_task_id}")
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
        seed_name: str,
        tool_count: int,
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
                    f"CrewAI dispatch completado para queue_id={task.queue_id} con seed "
                    f"{seed_name}, perfil {profile.name} ({profile.provider}/{profile.model}) "
                    f"en {latency_ms} ms [attempt={attempt_number}, fallback={fallback_used}, tools={tool_count}]"
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
