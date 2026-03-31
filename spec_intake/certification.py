from __future__ import annotations

from .architecture_synthesizer import synthesize_architecture
from .intake_guardrails import (
    INSUFFICIENT_INPUT,
    NEEDS_OPERATOR_REVIEW,
    READY_FOR_PLANNING,
    assess_confidence,
    build_question_budget,
    decide_human_escalation,
    determine_certification_status,
)
from .models import (
    ArchitectureSynthesis,
    CertifiedDocument,
    CertifiedInput,
    CertifiedTraceabilityEntry,
    ConfidenceAssessment,
    HumanEscalationDecision,
    ProjectBlueprint,
    QuestionBudget,
    SpecDocument,
    TechnologyGuidance,
)
from .flexible_inputs import SOURCE_INPUT_KIND_METADATA_KEY


CONTRACT_NAME = "mission_control_certified_input"
CONTRACT_VERSION = "1.0"


def infer_source_input_kind(source_documents: list[SpecDocument]) -> str:
    doc_types = {document.doc_type for document in source_documents}
    if {"requirements", "roadmap"} <= doc_types:
        return "formal_pair"
    if "conversation" in doc_types:
        return "chat_web"
    if "roadmap" in doc_types:
        return "roadmap_dossier"
    if source_documents:
        return "multi_artifact_brief"
    return "unknown"


def build_certified_input(
    blueprint: ProjectBlueprint,
    *,
    source_input_kind: str | None = None,
) -> CertifiedInput:
    resolved_input_kind = (
        source_input_kind
        or _extract_source_input_kind_override(blueprint.source_documents)
        or infer_source_input_kind(blueprint.source_documents)
    )
    technology_guidance = _build_technology_guidance(blueprint)
    architecture_synthesis = synthesize_architecture(
        blueprint,
        technology_guidance=technology_guidance,
        source_input_kind=resolved_input_kind,
    )
    assumptions = list(architecture_synthesis.assumptions)
    open_questions = list(architecture_synthesis.open_questions)
    traceability_map = _build_traceability_map(blueprint)
    confidence_assessment = assess_confidence(
        blueprint=blueprint,
        source_input_kind=resolved_input_kind,
        architecture_synthesis=architecture_synthesis,
        traceability_entries=len(traceability_map),
    )
    question_budget = build_question_budget(
        source_input_kind=resolved_input_kind,
        open_questions=open_questions,
    )
    human_escalation = decide_human_escalation(
        blueprint=blueprint,
        source_input_kind=resolved_input_kind,
        confidence_assessment=confidence_assessment,
        question_budget=question_budget,
    )
    certification_status = determine_certification_status(
        blueprint=blueprint,
        confidence_assessment=confidence_assessment,
        question_budget=question_budget,
        human_escalation=human_escalation,
    )
    confidence_score = confidence_assessment.score
    documents = _build_certified_documents(
        blueprint=blueprint,
        certification_status=certification_status,
        confidence_score=confidence_score,
        assumptions=assumptions,
        open_questions=open_questions,
        technology_guidance=technology_guidance,
        architecture_synthesis=architecture_synthesis,
        confidence_assessment=confidence_assessment,
        question_budget=question_budget,
        human_escalation=human_escalation,
    )

    return CertifiedInput(
        contract_name=CONTRACT_NAME,
        contract_version=CONTRACT_VERSION,
        source_input_kind=resolved_input_kind,
        certification_status=certification_status,
        confidence_score=confidence_score,
        summary=(
            f"Certified intake package for {blueprint.project_name}: "
            f"{len(blueprint.requirements)} requirements, "
            f"{len(blueprint.roadmap_epics)} epics, "
            f"{sum(len(epic.tickets) for epic in blueprint.roadmap_epics)} tickets."
        ),
        documents=documents,
        assumptions=assumptions,
        open_questions=open_questions,
        traceability_map=traceability_map,
        technology_guidance=technology_guidance,
        architecture_synthesis=architecture_synthesis,
        confidence_assessment=confidence_assessment,
        question_budget=question_budget,
        human_escalation=human_escalation,
    )


def _extract_source_input_kind_override(source_documents: list[SpecDocument]) -> str | None:
    for document in source_documents:
        source_input_kind = document.metadata.get(SOURCE_INPUT_KIND_METADATA_KEY)
        if source_input_kind:
            return source_input_kind
    return None

def _build_technology_guidance(blueprint: ProjectBlueprint) -> TechnologyGuidance:
    haystack = " ".join(
        [
            blueprint.project_name,
            *blueprint.capabilities,
            *(item.title for item in blueprint.requirements),
            *(item.summary for item in blueprint.requirements),
            *(document.title for document in blueprint.source_documents),
            *(section.title for document in blueprint.source_documents for section in document.sections),
            *(section.body for document in blueprint.source_documents for section in document.sections),
        ]
    ).lower()

    decision_notes = [
        (
            "Preferir Python para servicios backend, automatizacion, ingest, orchestration "
            "y tooling operador cuando sea compatible con el target del producto."
        ),
        (
            "Cuando el target requiera ecosistemas no compatibles con Python como runtime "
            "principal, elegir la tecnologia nativa o de mejor encaje y registrar la excepcion en ADRs."
        ),
    ]

    if "android" in haystack:
        decision_notes.append(
            "Si el alcance confirma Android nativo, evaluar Kotlin como tecnologia primaria del cliente."
        )
    if "ios" in haystack:
        decision_notes.append(
            "Si el alcance confirma iOS nativo, evaluar Swift como tecnologia primaria del cliente."
        )
    if all(token in haystack for token in ("windows", "linux", "mac")):
        decision_notes.append(
            "Para desktop multiplataforma, evaluar Python + Qt/PySide frente a alternativas como Tauri segun footprint, integracion con OS y operacion."
        )

    return TechnologyGuidance(
        philosophy="python_first",
        selection_policy=(
            "Prefer Python by default, but choose platform-native or ecosystem-standard "
            "technologies when Python is not a viable primary implementation path for the required targets."
        ),
        preferred_stack=[
            "Python for backend services and automation",
            "Python for orchestration and operator tooling",
        ],
        compatibility_exceptions=[
            "android_native",
            "ios_native",
            "targets_where_python_is_not_a_viable_primary_runtime",
        ],
        decision_notes=decision_notes,
    )


def _build_traceability_map(blueprint: ProjectBlueprint) -> list[CertifiedTraceabilityEntry]:
    requirements_document = next(
        (document for document in blueprint.source_documents if document.doc_type == "requirements"),
        None,
    )
    roadmap_document = next(
        (document for document in blueprint.source_documents if document.doc_type == "roadmap"),
        None,
    )
    traceability_map: list[CertifiedTraceabilityEntry] = []

    if requirements_document is not None:
        for requirement in blueprint.requirements:
            traceability_map.append(
                CertifiedTraceabilityEntry(
                    target_artifact="requirements.generated.md",
                    target_ref=requirement.requirement_id,
                    source_doc_type=requirements_document.doc_type,
                    source_path=requirements_document.path,
                    source_section=requirement.source_section,
                    rationale="Requirement normalized from the source requirements document.",
                )
            )

    if roadmap_document is not None:
        for epic in blueprint.roadmap_epics:
            traceability_map.append(
                CertifiedTraceabilityEntry(
                    target_artifact="roadmap.generated.md",
                    target_ref=epic.epic_id,
                    source_doc_type=roadmap_document.doc_type,
                    source_path=roadmap_document.path,
                    source_section=epic.name,
                    rationale="Epic normalized from the source roadmap document.",
                )
            )
            for ticket in epic.tickets:
                traceability_map.append(
                    CertifiedTraceabilityEntry(
                        target_artifact="roadmap.generated.md",
                        target_ref=ticket.ticket_id,
                        source_doc_type=roadmap_document.doc_type,
                        source_path=roadmap_document.path,
                        source_section=ticket.title,
                        rationale="Ticket normalized from the source roadmap document.",
                    )
                )

    return traceability_map


def _build_certified_documents(
    *,
    blueprint: ProjectBlueprint,
    certification_status: str,
    confidence_score: float,
    assumptions: list[str],
    open_questions: list[str],
    technology_guidance: TechnologyGuidance,
    architecture_synthesis: ArchitectureSynthesis,
    confidence_assessment: ConfidenceAssessment,
    question_budget: QuestionBudget,
    human_escalation: HumanEscalationDecision,
) -> list[CertifiedDocument]:
    requirements_source = next(
        (document for document in blueprint.source_documents if document.doc_type == "requirements"),
        None,
    )
    roadmap_source = next(
        (document for document in blueprint.source_documents if document.doc_type == "roadmap"),
        None,
    )

    return [
        CertifiedDocument(
            doc_type="requirements.generated.md",
            title="requirements.generated.md",
            content=_render_requirements_markdown(
                blueprint=blueprint,
                certification_status=certification_status,
                confidence_score=confidence_score,
                technology_guidance=technology_guidance,
                architecture_synthesis=architecture_synthesis,
                question_budget=question_budget,
                human_escalation=human_escalation,
            ),
            source_paths=[requirements_source.path] if requirements_source else [],
            source_sections=[item.source_section for item in blueprint.requirements],
        ),
        CertifiedDocument(
            doc_type="roadmap.generated.md",
            title="roadmap.generated.md",
            content=_render_roadmap_markdown(
                blueprint=blueprint,
                certification_status=certification_status,
                confidence_score=confidence_score,
            ),
            source_paths=[roadmap_source.path] if roadmap_source else [],
            source_sections=[epic.name for epic in blueprint.roadmap_epics],
        ),
        CertifiedDocument(
            doc_type="assumptions.md",
            title="assumptions.md",
            content=_render_list_document(
                title="Assumptions",
                project_name=blueprint.project_name,
                items=assumptions,
            ),
            source_paths=[document.path for document in blueprint.source_documents],
        ),
        CertifiedDocument(
            doc_type="nfrs.candidates.md",
            title="nfrs.candidates.md",
            content=_render_nfr_candidates_document(
                project_name=blueprint.project_name,
                architecture_synthesis=architecture_synthesis,
            ),
            source_paths=[document.path for document in blueprint.source_documents],
        ),
        CertifiedDocument(
            doc_type="technical_contracts.initial.md",
            title="technical_contracts.initial.md",
            content=_render_technical_contracts_document(
                project_name=blueprint.project_name,
                architecture_synthesis=architecture_synthesis,
            ),
            source_paths=[document.path for document in blueprint.source_documents],
        ),
        CertifiedDocument(
            doc_type="adr_bootstrap.md",
            title="adr_bootstrap.md",
            content=_render_adr_bootstrap_document(
                project_name=blueprint.project_name,
                architecture_synthesis=architecture_synthesis,
            ),
            source_paths=[document.path for document in blueprint.source_documents],
        ),
        CertifiedDocument(
            doc_type="open_questions.md",
            title="open_questions.md",
            content=_render_list_document(
                title="Open Questions",
                project_name=blueprint.project_name,
                items=open_questions or ["No open questions detected in the current certified input."],
                question_budget=question_budget,
                human_escalation=human_escalation,
            ),
            source_paths=[document.path for document in blueprint.source_documents],
        ),
        CertifiedDocument(
            doc_type="confidence_assessment.md",
            title="confidence_assessment.md",
            content=_render_confidence_assessment_document(
                project_name=blueprint.project_name,
                certification_status=certification_status,
                confidence_assessment=confidence_assessment,
                question_budget=question_budget,
                human_escalation=human_escalation,
            ),
            source_paths=[document.path for document in blueprint.source_documents],
        ),
    ]


def _render_requirements_markdown(
    *,
    blueprint: ProjectBlueprint,
    certification_status: str,
    confidence_score: float,
    technology_guidance: TechnologyGuidance,
    architecture_synthesis: ArchitectureSynthesis,
    question_budget: QuestionBudget,
    human_escalation: HumanEscalationDecision,
) -> str:
    lines = [
        f"# Requerimientos Formales - {blueprint.project_name}",
        "",
        f"**Proyecto**: {blueprint.project_name}",
        f"**Certification Status**: {certification_status}",
        f"**Confidence Score**: {confidence_score:.2f}",
        (
            f"**Question Budget**: {question_budget.open_questions_count}/"
            f"{question_budget.max_questions} abiertas"
        ),
        f"**Human Escalation**: {'required' if human_escalation.required else 'not_required'}",
        "",
        "## Tecnologia y Arquitectura",
        "",
        f"- Filosofia: {technology_guidance.philosophy}",
        f"- Politica: {technology_guidance.selection_policy}",
    ]
    for item in technology_guidance.preferred_stack:
        lines.append(f"- Preferencia: {item}")
    for item in technology_guidance.decision_notes:
        lines.append(f"- Nota: {item}")

    lines.extend(["", "## NFRs Candidatos", ""])
    for candidate in architecture_synthesis.nfr_candidates:
        lines.append(f"- {candidate.nfr_id} [{candidate.category}] {candidate.statement}")

    lines.extend(["", "## Capacidades", ""])
    if blueprint.capabilities:
        lines.extend(f"- {capability}" for capability in blueprint.capabilities)
    else:
        lines.append("- No se detectaron capacidades.")

    if blueprint.requirements:
        for requirement in blueprint.requirements:
            lines.extend(
                [
                    "",
                    f"## {requirement.requirement_id} · {requirement.title}",
                    "",
                    f"**Categoria**: {requirement.category}",
                    f"**Resumen**: {requirement.summary or 'Pendiente de completar.'}",
                ]
            )
            lines.append("")
            lines.append("**Restricciones**")
            if requirement.constraints:
                lines.extend(f"- {item}" for item in requirement.constraints)
            else:
                lines.append("- Sin restricciones explicitas detectadas.")
            lines.append("")
            lines.append("**Pistas de aceptacion**")
            if requirement.acceptance_hints:
                lines.extend(f"- {item}" for item in requirement.acceptance_hints)
            else:
                lines.append("- Sin pistas de aceptacion explicitas detectadas.")
    else:
        lines.extend(["", "## Requerimientos", "", "- No se detectaron requerimientos parseables."])

    return "\n".join(lines) + "\n"


def _render_roadmap_markdown(
    *,
    blueprint: ProjectBlueprint,
    certification_status: str,
    confidence_score: float,
) -> str:
    lines = [
        f"# Roadmap Formal - {blueprint.project_name}",
        "",
        f"**Proyecto**: {blueprint.project_name}",
        f"**Certification Status**: {certification_status}",
        f"**Confidence Score**: {confidence_score:.2f}",
    ]

    if not blueprint.roadmap_epics:
        lines.extend(["", "## EP-000 · Intake Incompleto", "", "- No se detectaron epics parseables."])
        return "\n".join(lines) + "\n"

    for epic in blueprint.roadmap_epics:
        lines.extend(
            [
                "",
                f"## {epic.epic_id} · {epic.name}",
                "",
                f"> Objetivo: {epic.objective or 'Pendiente de completar.'}",
            ]
        )
        if not epic.tickets:
            lines.extend(["", "- No se detectaron tickets parseables para esta epic."])
            continue

        for ticket in epic.tickets:
            lines.extend(
                [
                    "",
                    f"### {ticket.ticket_id} · {ticket.title}",
                    "```",
                    f"Tipo: {ticket.ticket_type or 'pendiente'}",
                    f"Prioridad: {ticket.priority or 'pendiente'}",
                    f"Est.: {ticket.estimate or 'pendiente'}",
                    f"Deps.: {', '.join(ticket.dependencies) if ticket.dependencies else 'ninguna'}",
                    "```",
                    "",
                    "**Descripción**",
                    ticket.description or "Pendiente de completar.",
                    "",
                    "**Criterios de aceptación**",
                ]
            )
            if ticket.acceptance_criteria:
                lines.extend(f"- [ ] {criterion}" for criterion in ticket.acceptance_criteria)
            else:
                lines.append("- [ ] Pendiente de completar.")

    return "\n".join(lines) + "\n"


def _render_list_document(
    *,
    title: str,
    project_name: str,
    items: list[str],
    question_budget: QuestionBudget | None = None,
    human_escalation: HumanEscalationDecision | None = None,
) -> str:
    lines = [
        f"# {title} - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        "",
    ]
    if question_budget is not None:
        lines.extend(
            [
                (
                    f"**Question Budget**: {question_budget.open_questions_count}/"
                    f"{question_budget.max_questions} abiertas"
                ),
                f"**Critical Questions**: {question_budget.critical_questions_count}",
                "",
            ]
        )
    if human_escalation is not None:
        lines.extend(
            [
                f"**Human Escalation**: {'required' if human_escalation.required else 'not_required'}",
                f"**Recommended Action**: {human_escalation.recommended_action}",
                "",
            ]
        )
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines) + "\n"


def _render_confidence_assessment_document(
    *,
    project_name: str,
    certification_status: str,
    confidence_assessment: ConfidenceAssessment,
    question_budget: QuestionBudget,
    human_escalation: HumanEscalationDecision,
) -> str:
    lines = [
        f"# Confidence Assessment - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        f"**Certification Status**: {certification_status}",
        f"**Confidence Score**: {confidence_assessment.score:.2f}",
        f"**Ready Threshold**: {confidence_assessment.ready_threshold:.2f}",
        f"**Review Threshold**: {confidence_assessment.review_threshold:.2f}",
        f"**Recommended Status**: {confidence_assessment.recommended_status}",
        "",
        "## Question Budget",
        "",
        f"- Open questions: {question_budget.open_questions_count}",
        f"- Max questions: {question_budget.max_questions}",
        f"- Critical questions: {question_budget.critical_questions_count}",
        f"- Remaining budget: {question_budget.remaining_questions}",
        f"- Budget exceeded: {'yes' if question_budget.exceeded else 'no'}",
        "",
        "## Human Escalation",
        "",
        f"- Required: {'yes' if human_escalation.required else 'no'}",
        f"- Recommended action: {human_escalation.recommended_action}",
    ]
    if human_escalation.reasons:
        lines.extend(["", "## Escalation Reasons", ""])
        lines.extend(f"- {reason}" for reason in human_escalation.reasons)
    if confidence_assessment.factors:
        lines.extend(["", "## Factors", ""])
        for factor in confidence_assessment.factors:
            lines.append(f"- {factor.label}: {factor.impact:+.2f} · {factor.rationale}")
    return "\n".join(lines) + "\n"


def _render_nfr_candidates_document(
    *,
    project_name: str,
    architecture_synthesis: ArchitectureSynthesis,
) -> str:
    lines = [
        f"# NFR Candidates - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        f"**Estilo arquitectonico**: {architecture_synthesis.architectural_style}",
        "",
        architecture_synthesis.system_context,
        "",
    ]
    for candidate in architecture_synthesis.nfr_candidates:
        lines.extend(
            [
                f"## {candidate.nfr_id} · {candidate.category}",
                "",
                candidate.statement,
                "",
                f"Rationale: {candidate.rationale}",
            ]
        )
        if candidate.source_signals:
            lines.append(f"Signals: {', '.join(candidate.source_signals)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_technical_contracts_document(
    *,
    project_name: str,
    architecture_synthesis: ArchitectureSynthesis,
) -> str:
    lines = [
        f"# Technical Contracts - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        "",
    ]
    for contract in architecture_synthesis.technical_contracts:
        lines.extend(
            [
                f"## {contract.contract_id} · {contract.name}",
                "",
                f"**Boundary**: {contract.boundary}",
                contract.summary,
                "",
                "**Responsibilities**",
            ]
        )
        lines.extend(f"- {item}" for item in contract.responsibilities)
        if contract.source_signals:
            lines.extend(["", f"**Signals**: {', '.join(contract.source_signals)}"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_adr_bootstrap_document(
    *,
    project_name: str,
    architecture_synthesis: ArchitectureSynthesis,
) -> str:
    lines = [
        f"# ADR Bootstrap - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        "",
    ]
    for decision in architecture_synthesis.adr_bootstrap:
        lines.extend(
            [
                f"## {decision.adr_id} · {decision.title}",
                "",
                f"**Status**: {decision.status}",
                f"**Decision**: {decision.decision}",
                "",
                f"**Rationale**: {decision.rationale}",
            ]
        )
        if decision.follow_up_questions:
            lines.extend(["", "**Follow-up Questions**"])
            lines.extend(f"- {question}" for question in decision.follow_up_questions)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
