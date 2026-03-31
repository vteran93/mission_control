from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SpecSection:
    heading_level: int
    title: str
    body: str


@dataclass(frozen=True)
class SpecDocument:
    doc_type: str
    path: str
    title: str
    metadata: dict[str, str] = field(default_factory=dict)
    sections: list[SpecSection] = field(default_factory=list)


@dataclass(frozen=True)
class RequirementItem:
    requirement_id: str
    title: str
    source_section: str
    category: str
    summary: str
    constraints: list[str] = field(default_factory=list)
    acceptance_hints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoadmapTicket:
    ticket_id: str
    title: str
    epic_id: str | None
    epic_name: str | None
    ticket_type: str | None
    priority: str | None
    estimate: str | None
    dependencies: list[str] = field(default_factory=list)
    description: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoadmapEpic:
    epic_id: str
    name: str
    objective: str = ""
    tickets: list[RoadmapTicket] = field(default_factory=list)


@dataclass(frozen=True)
class CertifiedTraceabilityEntry:
    target_artifact: str
    target_ref: str
    source_doc_type: str
    source_path: str
    source_section: str
    rationale: str


@dataclass(frozen=True)
class TechnologyGuidance:
    philosophy: str
    selection_policy: str
    preferred_stack: list[str] = field(default_factory=list)
    compatibility_exceptions: list[str] = field(default_factory=list)
    decision_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CertifiedDocument:
    doc_type: str
    title: str
    content: str
    source_paths: list[str] = field(default_factory=list)
    source_sections: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CertifiedInput:
    contract_name: str
    contract_version: str
    source_input_kind: str
    certification_status: str
    confidence_score: float
    summary: str
    documents: list[CertifiedDocument] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    traceability_map: list[CertifiedTraceabilityEntry] = field(default_factory=list)
    technology_guidance: TechnologyGuidance | None = None


@dataclass(frozen=True)
class ProjectBlueprint:
    project_name: str
    source_documents: list[SpecDocument]
    capabilities: list[str]
    requirements: list[RequirementItem]
    roadmap_epics: list[RoadmapEpic]
    acceptance_items: list[str]
    delivery_guardrails: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    certified_input: CertifiedInput | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["summary"] = {
            "requirements_count": len(self.requirements),
            "epics_count": len(self.roadmap_epics),
            "tickets_count": sum(len(epic.tickets) for epic in self.roadmap_epics),
            "acceptance_items_count": len(self.acceptance_items),
            "issues_count": len(self.issues),
        }
        return payload
