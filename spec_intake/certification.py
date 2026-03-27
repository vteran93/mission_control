from __future__ import annotations

from .models import (
    CertifiedDocument,
    CertifiedInput,
    CertifiedTraceabilityEntry,
    ProjectBlueprint,
    SpecDocument,
    TechnologyGuidance,
)


CONTRACT_NAME = "mission_control_certified_input"
CONTRACT_VERSION = "1.0"
READY_FOR_PLANNING = "ready_for_planning"
NEEDS_OPERATOR_REVIEW = "needs_operator_review"
INSUFFICIENT_INPUT = "insufficient_input"


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
    resolved_input_kind = source_input_kind or infer_source_input_kind(blueprint.source_documents)
    certification_status = _determine_certification_status(blueprint)
    confidence_score = _compute_confidence_score(blueprint)
    technology_guidance = _build_technology_guidance(blueprint)
    assumptions = _build_assumptions(resolved_input_kind)
    open_questions = _build_open_questions(blueprint)
    traceability_map = _build_traceability_map(blueprint)
    documents = _build_certified_documents(
        blueprint=blueprint,
        certification_status=certification_status,
        confidence_score=confidence_score,
        assumptions=assumptions,
        open_questions=open_questions,
        technology_guidance=technology_guidance,
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
    )


def _determine_certification_status(blueprint: ProjectBlueprint) -> str:
    if not blueprint.requirements or not blueprint.roadmap_epics:
        return INSUFFICIENT_INPUT
    if blueprint.issues:
        return NEEDS_OPERATOR_REVIEW
    return READY_FOR_PLANNING


def _compute_confidence_score(blueprint: ProjectBlueprint) -> float:
    score = 1.0
    if not blueprint.requirements:
        score -= 0.45
    if not blueprint.roadmap_epics:
        score -= 0.45
    if any(not epic.tickets for epic in blueprint.roadmap_epics):
        score -= 0.10
    score -= min(0.30, len(blueprint.issues) * 0.08)
    if not blueprint.acceptance_items:
        score -= 0.05
    return round(max(0.0, min(1.0, score)), 2)


def _build_assumptions(source_input_kind: str) -> list[str]:
    assumptions = [
        (
            "La seleccion tecnologica sigue una politica python-first para backend, "
            "automatizacion y orquestacion, salvo incompatibilidad real con la "
            "plataforma o el runtime objetivo."
        ),
        (
            "Cualquier excepcion a python-first debe documentarse como decision "
            "arquitectonica explicita antes de pasar a delivery."
        ),
    ]
    if source_input_kind != "formal_pair":
        assumptions.append(
            "Este paquete certificado representa una normalizacion derivada y requiere aprobacion del operador."
        )
    return assumptions


def _build_open_questions(blueprint: ProjectBlueprint) -> list[str]:
    if blueprint.issues:
        return list(blueprint.issues)
    return []


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
            doc_type="open_questions.md",
            title="open_questions.md",
            content=_render_list_document(
                title="Open Questions",
                project_name=blueprint.project_name,
                items=open_questions or ["No open questions detected in the current certified input."],
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
) -> str:
    lines = [
        f"# Requerimientos Formales - {blueprint.project_name}",
        "",
        f"**Proyecto**: {blueprint.project_name}",
        f"**Certification Status**: {certification_status}",
        f"**Confidence Score**: {confidence_score:.2f}",
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


def _render_list_document(*, title: str, project_name: str, items: list[str]) -> str:
    lines = [
        f"# {title} - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        "",
    ]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines) + "\n"
