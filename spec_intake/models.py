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
class NfrCandidate:
    nfr_id: str
    category: str
    statement: str
    rationale: str
    source_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TechnicalContract:
    contract_id: str
    name: str
    boundary: str
    summary: str
    responsibilities: list[str] = field(default_factory=list)
    source_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AdrBootstrapDecision:
    adr_id: str
    title: str
    status: str
    decision: str
    rationale: str
    follow_up_questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArchitectureSynthesis:
    summary: str
    architectural_style: str
    system_context: str
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    nfr_candidates: list[NfrCandidate] = field(default_factory=list)
    technical_contracts: list[TechnicalContract] = field(default_factory=list)
    adr_bootstrap: list[AdrBootstrapDecision] = field(default_factory=list)


@dataclass(frozen=True)
class ConfidenceFactor:
    label: str
    impact: float
    rationale: str


@dataclass(frozen=True)
class ConfidenceAssessment:
    score: float
    ready_threshold: float
    review_threshold: float
    recommended_status: str
    factors: list[ConfidenceFactor] = field(default_factory=list)


@dataclass(frozen=True)
class QuestionBudget:
    max_questions: int
    open_questions_count: int
    critical_questions_count: int
    remaining_questions: int
    exceeded: bool
    blocking_questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HumanEscalationDecision:
    required: bool
    recommended_action: str
    reasons: list[str] = field(default_factory=list)


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
    architecture_synthesis: ArchitectureSynthesis | None = None
    confidence_assessment: ConfidenceAssessment | None = None
    question_budget: QuestionBudget | None = None
    human_escalation: HumanEscalationDecision | None = None


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
