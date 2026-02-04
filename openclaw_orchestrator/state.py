"""State definitions for the OpenClaw LangGraph orchestrator."""

from __future__ import annotations

from typing import Literal, TypedDict


class MissionState(TypedDict):
    """Shared state exchanged across LangGraph nodes."""

    ticket_id: str
    requirements: str
    disk_checkpoint: str
    code_diff: str
    revision_count: int
    next_step: Literal["developer", "qa", "human_intervention", "deploy"]
