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
    from_agent: str
    content: str
    priority: str
    retry_count: int


@dataclass(frozen=True)
class DispatchResult:
    queue_id: int
    success: bool
    detail: str
    runtime_name: str
    external_ref: str | None = None


class RuntimeProvider(Protocol):
    name: str

    def healthcheck(self) -> ProviderHealth:
        """Return the health state of a runtime dependency."""


class TaskExecutor(Protocol):
    name: str

    def dispatch(self, task: DispatchTask) -> DispatchResult:
        """Run or hand off a queued task to the configured runtime."""
