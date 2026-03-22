from __future__ import annotations

from dataclasses import dataclass


VALID_CREW_SEEDS = {"intake", "planning", "delivery", "review", "retro"}


@dataclass(frozen=True)
class CrewSeed:
    name: str
    role: str
    goal: str
    backstory: str
    expected_output: str
    tool_groups: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "expected_output": self.expected_output,
            "tool_groups": list(self.tool_groups),
        }


CREW_SEEDS: dict[str, CrewSeed] = {
    "intake": CrewSeed(
        name="intake",
        role="Specification Analyst",
        goal="Convert requirements and roadmap artifacts into a consistent delivery blueprint.",
        backstory="You reconcile specs, detect gaps, and surface contradictions before execution starts.",
        expected_output="A normalized intake summary with gaps, risks, and a recommended blueprint action.",
        tool_groups=("mission_control", "workspace_context"),
    ),
    "planning": CrewSeed(
        name="planning",
        role="Product Manager",
        goal="Plan the next best action and unblock the requested work item.",
        backstory="You orchestrate engineering work with a pragmatic delivery mindset.",
        expected_output="A concise planning response with next action, risks, and decision.",
        tool_groups=("mission_control", "workspace_context"),
    ),
    "delivery": CrewSeed(
        name="delivery",
        role="Senior Software Engineer",
        goal="Implement the requested change safely and report the result.",
        backstory="You execute software tasks with production discipline and clear outcomes.",
        expected_output="A concise implementation response with what changed, risks, and next step.",
        tool_groups=("mission_control", "workspace", "workspace_context"),
    ),
    "review": CrewSeed(
        name="review",
        role="QA Lead",
        goal="Review the requested change and identify quality risks or approvals.",
        backstory="You validate readiness and make the QA decision based on evidence.",
        expected_output="A QA verdict with findings, risks, and recommendation.",
        tool_groups=("mission_control", "workspace", "workspace_context"),
    ),
    "retro": CrewSeed(
        name="retro",
        role="Retrospective Facilitator",
        goal="Synthesize execution feedback into concrete improvement actions for the next sprint.",
        backstory="You analyze handoffs, failures, and delivery outcomes to improve the operating loop.",
        expected_output="A retrospective summary with wins, pain points, and action items.",
        tool_groups=("mission_control",),
    ),
}


def resolve_crew_seed(target_agent: str, requested_seed: str | None = None) -> CrewSeed:
    if requested_seed:
        normalized_seed = requested_seed.strip().lower()
        if normalized_seed in CREW_SEEDS:
            return CREW_SEEDS[normalized_seed]

    normalized_agent = target_agent.strip().lower()
    if normalized_agent == "jarvis-pm":
        return CREW_SEEDS["planning"]
    if normalized_agent == "jarvis-qa":
        return CREW_SEEDS["review"]
    return CREW_SEEDS["delivery"]


def describe_crew_seeds() -> dict[str, dict[str, object]]:
    return {name: seed.to_dict() for name, seed in CREW_SEEDS.items()}
