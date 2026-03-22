from __future__ import annotations

import threading
from dataclasses import asdict
from time import sleep
from typing import Any

from config import Settings

from .crewai_executor import CrewAIExecutor
from .contracts import DispatchResult, DispatchTask
from .crew_seeds import describe_crew_seeds
from .dispatcher import DatabaseQueueDispatcher
from .legacy_bridge import LegacyGatewayExecutor
from .model_registry import ModelRegistry
from .providers import BedrockProvider, CrewAIProvider, GitHubProvider, OllamaProvider
from .toolkit import RuntimeToolCatalog


class DisabledExecutor:
    name = "disabled"
    available = False

    def dispatch(self, task: DispatchTask) -> DispatchResult:
        return DispatchResult(
            queue_id=task.queue_id,
            success=False,
            detail="No hay executor configurado para el runtime",
            runtime_name=self.name,
        )


class AgenticRuntime:
    """Runtime bootstrap for the CrewAI migration.

    Phase 0 keeps this lightweight: DB queue management, provider healthchecks
    and an optional compatibility bridge. Full CrewAI execution lands later.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dispatcher = DatabaseQueueDispatcher()
        self.model_registry = ModelRegistry(settings)
        self.tool_catalog = RuntimeToolCatalog(settings)
        self.providers = [
            CrewAIProvider(),
            OllamaProvider(settings.ollama),
            BedrockProvider(settings.bedrock),
            GitHubProvider(settings.github),
        ]
        self.executor = self._build_executor()
        self._dispatch_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def dispatch_ready(self) -> bool:
        return (
            self.settings.runtime.enabled
            and self.executor.name != "disabled"
            and getattr(self.executor, "available", True)
        )

    def _build_executor(self):
        if self.settings.runtime.dispatcher_executor == "crewai":
            return CrewAIExecutor(self.model_registry, tool_catalog=self.tool_catalog)
        if (
            self.settings.runtime.dispatcher_executor == "legacy_bridge"
            and self.settings.runtime.enable_legacy_bridge
        ):
            return LegacyGatewayExecutor(
                gateway_url=self.settings.runtime.legacy_gateway_url,
                gateway_token=self.settings.runtime.legacy_gateway_token,
            )
        return DisabledExecutor()

    def healthcheck(self) -> dict[str, Any]:
        return {
            "runtime": {
                "enabled": self.settings.runtime.enabled,
                "dispatch_ready": self.dispatch_ready,
                "dispatcher_autostart": self.settings.runtime.dispatcher_autostart,
                "dispatcher_executor": self.executor.name,
                "dispatcher_batch_size": self.settings.runtime.dispatcher_batch_size,
                "dispatcher_recover_after_seconds": self.settings.runtime.dispatcher_recover_after_seconds,
                "dispatcher_escalate_after_retries": self.settings.runtime.dispatcher_escalate_after_retries,
                "dispatcher_enable_fallback": self.settings.runtime.dispatcher_enable_fallback,
                "legacy_bridge_enabled": self.settings.runtime.enable_legacy_bridge,
                "executor_available": getattr(self.executor, "available", True),
            },
            "queue": self.dispatcher.queue_summary(
                stale_after_seconds=self.settings.runtime.dispatcher_recover_after_seconds
            ),
            "model_registry": self.model_registry.describe(),
            "toolkit": {
                "tool_count": len(self.tool_catalog.describe()),
                "tools": self.tool_catalog.describe(),
                "crew_seeds": describe_crew_seeds(),
            },
            "providers": {
                provider.name: asdict(provider.healthcheck()) for provider in self.providers
            },
        }

    def process_pending(
        self,
        *,
        limit: int | None = None,
        target_agent: str | None = None,
        queue_entry_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.dispatch_ready:
            return []

        queue_entries = self.dispatcher.claim_pending_entries(
            limit=limit or self.settings.runtime.dispatcher_batch_size,
            target_agent=target_agent,
            queue_entry_id=queue_entry_id,
        )
        dispatch_results: list[dict[str, Any]] = []
        for queue_entry in queue_entries:
            result = self.executor.dispatch(
                DispatchTask(
                    queue_id=queue_entry.id,
                    target_agent=queue_entry.target_agent,
                    message_id=queue_entry.message_id,
                    project_blueprint_id=queue_entry.project_blueprint_id,
                    delivery_task_id=queue_entry.delivery_task_id,
                    from_agent=queue_entry.from_agent,
                    content=queue_entry.content,
                    priority=queue_entry.priority,
                    retry_count=queue_entry.retry_count or 0,
                    crew_seed=queue_entry.crew_seed,
                )
            )
            self.dispatcher.apply_result(
                queue_entry,
                success=result.success,
                detail=result.detail,
                runtime_session_key=result.external_ref,
                runtime_metadata=result.runtime_metadata,
            )
            dispatch_results.append(asdict(result))
        return dispatch_results

    def recover_stale_processing(
        self,
        *,
        stale_after_seconds: float | None = None,
        target_agent: str | None = None,
    ) -> list[dict[str, Any]]:
        queue_entries = self.dispatcher.recover_abandoned_entries(
            stale_after_seconds=(
                stale_after_seconds or self.settings.runtime.dispatcher_recover_after_seconds
            ),
            target_agent=target_agent,
        )
        return [self.dispatcher.serialize(queue_entry) for queue_entry in queue_entries]

    def describe_tools(self) -> list[dict[str, str]]:
        return self.tool_catalog.describe()

    @staticmethod
    def describe_crew_seeds() -> dict[str, dict[str, object]]:
        return describe_crew_seeds()

    def start_background_dispatcher(self, app) -> bool:
        if (
            not self.settings.runtime.dispatcher_autostart
            or not self.dispatch_ready
            or self._dispatch_thread is not None
        ):
            return False

        def run_dispatch_loop() -> None:
            with app.app_context():
                while not self._stop_event.is_set():
                    self.process_pending()
                    sleep(self.settings.runtime.dispatcher_poll_interval_seconds)

        self._dispatch_thread = threading.Thread(
            target=run_dispatch_loop,
            name="mission-control-dispatcher",
            daemon=True,
        )
        self._dispatch_thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
