"""Mission Control OpenClaw LangGraph orchestrator package."""

from .bridge import OpenClawBridge, OpenClawSnapshot
from .skill import build_skill_definition, register_skill
from .state import MissionState


def build_graph(*args, **kwargs):
    """Lazy import wrapper for graph construction."""

    from .graph import build_graph as _build_graph

    return _build_graph(*args, **kwargs)


def build_app(*args, **kwargs):
    """Lazy import wrapper for graph compilation."""

    from .graph import build_app as _build_app

    return _build_app(*args, **kwargs)


__all__ = [
    "MissionState",
    "OpenClawBridge",
    "OpenClawSnapshot",
    "build_graph",
    "build_app",
    "build_skill_definition",
    "register_skill",
]
