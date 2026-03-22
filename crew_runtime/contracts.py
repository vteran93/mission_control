from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    ok: bool
    configured: bool
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchTask:
    queue_id: int
    target_agent: str
    message_id: int
    project_blueprint_id: int | None
    delivery_task_id: int | None
    from_agent: str
    content: str
    priority: str
    retry_count: int
    crew_seed: str | None = None


@dataclass(frozen=True)
class DispatchResult:
    queue_id: int
    success: bool
    detail: str
    runtime_name: str
    external_ref: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    attempts: int = 0
    fallback_used: bool = False
    runtime_metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeProvider(Protocol):
    name: str

    def healthcheck(self) -> ProviderHealth:
        """Return the health state of a runtime dependency."""


class TaskExecutor(Protocol):
    name: str

    def dispatch(self, task: DispatchTask) -> DispatchResult:
        """Run or hand off a queued task to the configured runtime."""
