"""LangGraph definition for the OpenClaw Supervisor-Worker orchestrator."""

from __future__ import annotations

import os
from typing import Callable

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from .bridge import OpenClawBridge
from .nodes import (
    QAReviewFn,
    DecisionFn,
    default_supervisor_decision,
    deploy_node,
    developer_node,
    human_intervention_node,
    qa_node,
    supervisor_node,
)
from .state import MissionState


def _route_next(state: MissionState) -> str:
    """Route to the next node with a safety kill switch."""

    if state["revision_count"] > 3:
        return "human_intervention"
    return state["next_step"]


def build_graph(
    bridge: OpenClawBridge,
    decision_fn: DecisionFn | None = None,
    qa_review: QAReviewFn | None = None,
) -> StateGraph:
    """Create the LangGraph topology for the orchestrator."""

    graph = StateGraph(MissionState)
    graph.add_node(
        "supervisor",
        lambda state: supervisor_node(
            state, bridge, decision_fn=decision_fn or default_supervisor_decision
        ),
    )
    graph.add_node("developer", lambda state: developer_node(state, bridge))
    graph.add_node("qa", lambda state: qa_node(state, qa_review=qa_review))
    graph.add_node("deploy", deploy_node)
    graph.add_node("human_intervention", human_intervention_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_next,
        {
            "developer": "developer",
            "qa": "qa",
            "deploy": "deploy",
            "human_intervention": "human_intervention",
        },
    )
    graph.add_edge("developer", "supervisor")
    graph.add_edge("qa", "supervisor")
    graph.add_edge("deploy", END)
    graph.add_edge("human_intervention", END)
    return graph


def build_app(
    bridge: OpenClawBridge,
    sqlite_path: str | None = None,
    decision_fn: DecisionFn | None = None,
    qa_review: QAReviewFn | None = None,
):
    """Compile the graph with SqliteSaver persistence."""

    sqlite_path = sqlite_path or os.environ.get(
        "OPENCLAW_SQLITE_PATH", os.path.join(bridge.state_dir, "orchestrator.sqlite")
    )
    saver = SqliteSaver.from_conn_string(sqlite_path)
    graph = build_graph(bridge, decision_fn=decision_fn, qa_review=qa_review)
    return graph.compile(checkpointer=saver)
