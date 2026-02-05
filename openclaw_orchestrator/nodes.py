"""LangGraph nodes for the Supervisor-Worker orchestration pattern."""

from __future__ import annotations

from typing import Callable, Mapping

from .bridge import OpenClawBridge
from .state import MissionState


DecisionFn = Callable[[MissionState, Mapping[str, str]], str]
QAReviewFn = Callable[[str], str]


def default_supervisor_decision(state: MissionState, snapshot: Mapping[str, str]) -> str:
    """Default decision policy when no LLM supervisor is injected."""

    if state["revision_count"] > 3:
        return "human_intervention"
    if not snapshot.get("filesystem_diffs"):
        return "developer"
    return "qa"


def supervisor_node(
    state: MissionState,
    bridge: OpenClawBridge,
    decision_fn: DecisionFn | None = None,
) -> MissionState:
    """Supervisor node that audits disk state and chooses the next step."""

    snapshot = bridge.snapshot()
    decision = (decision_fn or default_supervisor_decision)(
        state,
        {
            "disk_checkpoint": snapshot.disk_checkpoint,
            "filesystem_diffs": snapshot.filesystem_diffs,
            "last_terminal_output": snapshot.last_terminal_output,
        },
    )

    return {
        **state,
        "disk_checkpoint": snapshot.disk_checkpoint,
        "code_diff": snapshot.filesystem_diffs,
        "revision_count": state["revision_count"] + 1,
        "next_step": decision,
    }


def developer_node(state: MissionState, bridge: OpenClawBridge) -> MissionState:
    """Developer node that delegates build tasks to OpenClaw."""

    bridge.dispatch_to_claw("developer", state["requirements"])
    snapshot = bridge.snapshot()
    return {
        **state,
        "disk_checkpoint": snapshot.disk_checkpoint,
        "code_diff": snapshot.filesystem_diffs,
        "next_step": "qa",
    }


def qa_node(
    state: MissionState,
    qa_review: QAReviewFn | None = None,
) -> MissionState:
    """QA node constrained to requirements and code diff only."""

    prompt = (
        "REQUIREMENTS:\n"
        f"{state['requirements']}\n\n"
        "CODE_DIFF:\n"
        f"{state['code_diff']}\n"
    )

    review_output = qa_review(prompt) if qa_review else "QA review pending."
    return {
        **state,
        "next_step": "deploy" if "APPROVED" in review_output else "developer",
    }


def human_intervention_node(state: MissionState) -> MissionState:
    """Terminal node that flags human intervention."""

    return {
        **state,
        "next_step": "human_intervention",
    }


def deploy_node(state: MissionState) -> MissionState:
    """Deployment node placeholder."""

    return {
        **state,
        "next_step": "deploy",
    }
