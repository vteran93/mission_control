from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SpecDocument
from .parser import extract_bullets, parse_spec_document, parse_spec_text, summarize_section


FORMAL_PAIR = "formal_pair"
ROADMAP_DOSSIER = "roadmap_dossier"
MULTI_ARTIFACT_BRIEF = "multi_artifact_brief"
USE_CASE_ONLY = "use_case_only"

SOURCE_INPUT_KIND_METADATA_KEY = "Mission Control Source Input Kind"
SOURCE_ARTIFACT_PATHS_METADATA_KEY = "Mission Control Source Artifact Paths"

FORMAL_ROADMAP_PATTERN = re.compile(r"^##\s+EP-\d+\s+[·-]\s+.+$", flags=re.MULTILINE)
PHASE_ROADMAP_PATTERN = re.compile(r"^##\s+Fase\b.+$", flags=re.IGNORECASE | re.MULTILINE)
TICKET_PATTERN = re.compile(r"^###\s+TICKET-\d+\s+[·-]\s+.+$", flags=re.MULTILINE)
ROADMAP_FILENAME_PATTERN = re.compile(r"(roadmap|plan|fases|phases)", flags=re.IGNORECASE)
REQUIREMENTS_FILENAME_PATTERN = re.compile(
    r"(requirements|requerimientos|prd|use_case|caso_de_uso|casos_de_uso)",
    flags=re.IGNORECASE,
)
DIAGRAM_FILENAME_PATTERN = re.compile(r"(diagram|diagrama|class)", flags=re.IGNORECASE)
EXCLUDED_REQUIREMENTS_TITLES = {
    "archivos impactados",
    "criterio de salida",
    "roadmap por fases",
    "cambios tecnicos concretos por modulo",
    "secuencia recomendada de entrega",
    "resultado esperado al terminar la fase inicial",
    "fuentes oficiales usadas",
    "diagrama de clases",
}
PHASE_TITLE_PATTERN = re.compile(r"^Fase\s+([0-9]+[A-Z]?)\.?\s*(.+)?$", flags=re.IGNORECASE)


@dataclass(frozen=True)
class InputArtifact:
    artifact_id: str
    display_name: str
    path: str | None
    content: str
    role_hint: str | None = None


@dataclass(frozen=True)
class InputShapeClassification:
    shape_kind: str
    rationale: str
    artifacts: list[InputArtifact]
    requirements_artifact: InputArtifact | None = None
    roadmap_artifact: InputArtifact | None = None


def normalize_input_artifacts(input_artifacts: list[Any]) -> list[InputArtifact]:
    normalized: list[InputArtifact] = []
    for index, artifact in enumerate(input_artifacts, start=1):
        artifact_id = f"artifact-{index:03d}"
        if isinstance(artifact, (str, Path)):
            resolved_path = Path(artifact).expanduser().resolve()
            content = resolved_path.read_text(encoding="utf-8")
            normalized.append(
                InputArtifact(
                    artifact_id=artifact_id,
                    display_name=resolved_path.name,
                    path=str(resolved_path),
                    content=content,
                    role_hint=_infer_role_hint(resolved_path.name, content, explicit_role=None),
                )
            )
            continue

        if not isinstance(artifact, dict):
            raise ValueError("Each input artifact must be a path string or an object.")

        raw_path = artifact.get("path")
        content = artifact.get("content")
        label = artifact.get("label")
        explicit_role = artifact.get("role")
        resolved_path: str | None = None

        if raw_path:
            path_obj = Path(raw_path).expanduser().resolve()
            content = content or path_obj.read_text(encoding="utf-8")
            resolved_path = str(path_obj)
            display_name = label or path_obj.name
        elif content:
            display_name = label or f"{artifact_id}.md"
        else:
            raise ValueError("Each input artifact object requires either path or content.")

        normalized.append(
            InputArtifact(
                artifact_id=artifact_id,
                display_name=display_name,
                path=resolved_path,
                content=content,
                role_hint=_infer_role_hint(display_name, content, explicit_role=explicit_role),
            )
        )

    if not normalized:
        raise ValueError("At least one input artifact is required.")
    return normalized


def classify_input_artifacts(input_artifacts: list[Any]) -> InputShapeClassification:
    artifacts = normalize_input_artifacts(input_artifacts)
    requirements_artifact = next(
        (artifact for artifact in artifacts if artifact.role_hint == "requirements"),
        None,
    )
    roadmap_artifact = next(
        (
            artifact
            for artifact in artifacts
            if artifact.role_hint == "roadmap"
            or _looks_like_formal_roadmap(artifact.content)
            or _looks_like_phase_roadmap(artifact.content)
        ),
        None,
    )

    if (
        requirements_artifact is not None
        and roadmap_artifact is not None
        and (_looks_like_formal_roadmap(roadmap_artifact.content) or roadmap_artifact.role_hint == "roadmap")
    ):
        return InputShapeClassification(
            shape_kind=FORMAL_PAIR,
            rationale="Detected explicit requirements and roadmap artifacts.",
            artifacts=artifacts,
            requirements_artifact=requirements_artifact,
            roadmap_artifact=roadmap_artifact,
        )

    if roadmap_artifact is not None:
        return InputShapeClassification(
            shape_kind=ROADMAP_DOSSIER,
            rationale="Detected a roadmap-style dossier without a canonical requirements document.",
            artifacts=artifacts,
            requirements_artifact=requirements_artifact,
            roadmap_artifact=roadmap_artifact,
        )

    if len(artifacts) == 1:
        return InputShapeClassification(
            shape_kind=USE_CASE_ONLY,
            rationale="Detected a single open brief or use-case artifact.",
            artifacts=artifacts,
            requirements_artifact=requirements_artifact,
            roadmap_artifact=None,
        )

    return InputShapeClassification(
        shape_kind=MULTI_ARTIFACT_BRIEF,
        rationale="Detected multiple supporting artifacts that require normalization into certified input.",
        artifacts=artifacts,
        requirements_artifact=requirements_artifact,
        roadmap_artifact=roadmap_artifact,
    )


def build_source_documents_from_artifacts(
    input_artifacts: list[Any],
) -> tuple[InputShapeClassification, list[SpecDocument]]:
    classification = classify_input_artifacts(input_artifacts)

    if classification.shape_kind == FORMAL_PAIR:
        documents = _build_documents_for_formal_pair(classification)
        return classification, documents

    context_documents = [
        _artifact_to_document(artifact, doc_type=_infer_context_doc_type(artifact))
        for artifact in classification.artifacts
    ]
    project_name = _infer_project_name(context_documents, classification)
    requirements_document = _build_synthesized_requirements_document(
        project_name=project_name,
        classification=classification,
        context_documents=context_documents,
    )
    roadmap_document = _build_synthesized_roadmap_document(
        project_name=project_name,
        classification=classification,
        context_documents=context_documents,
    )
    documents = [requirements_document, roadmap_document, *context_documents]
    return classification, documents


def _build_documents_for_formal_pair(classification: InputShapeClassification) -> list[SpecDocument]:
    if classification.requirements_artifact is None or classification.roadmap_artifact is None:
        raise ValueError("Formal pair classification requires both requirements and roadmap artifacts.")

    documents = [
        _with_certification_metadata(
            _artifact_to_document(classification.requirements_artifact, doc_type="requirements"),
            classification=classification,
        ),
        _with_certification_metadata(
            _artifact_to_document(classification.roadmap_artifact, doc_type="roadmap"),
            classification=classification,
        ),
    ]

    for artifact in classification.artifacts:
        if artifact in {classification.requirements_artifact, classification.roadmap_artifact}:
            continue
        documents.append(_artifact_to_document(artifact, doc_type=_infer_context_doc_type(artifact)))
    return documents


def _artifact_to_document(artifact: InputArtifact, *, doc_type: str) -> SpecDocument:
    if artifact.path:
        return parse_spec_document(artifact.path, doc_type=doc_type)
    synthetic_path = f"memory://mission-control/{artifact.artifact_id}/{artifact.display_name}"
    return parse_spec_text(artifact.content, doc_type=doc_type, path=synthetic_path)


def _with_certification_metadata(
    document: SpecDocument,
    *,
    classification: InputShapeClassification,
) -> SpecDocument:
    metadata = dict(document.metadata)
    metadata[SOURCE_INPUT_KIND_METADATA_KEY] = classification.shape_kind
    metadata[SOURCE_ARTIFACT_PATHS_METADATA_KEY] = " | ".join(
        artifact.path or artifact.display_name for artifact in classification.artifacts
    )
    return SpecDocument(
        doc_type=document.doc_type,
        path=document.path,
        title=document.title,
        metadata=metadata,
        sections=document.sections,
    )


def _infer_role_hint(display_name: str, content: str, *, explicit_role: str | None) -> str | None:
    if explicit_role:
        return explicit_role.strip().lower()

    if REQUIREMENTS_FILENAME_PATTERN.search(display_name):
        return "requirements"
    if ROADMAP_FILENAME_PATTERN.search(display_name):
        return "roadmap"
    if DIAGRAM_FILENAME_PATTERN.search(display_name):
        return "diagram"
    if _looks_like_formal_roadmap(content) or _looks_like_phase_roadmap(content):
        return "roadmap"
    return None


def _infer_context_doc_type(artifact: InputArtifact) -> str:
    if artifact.role_hint == "diagram":
        return "architecture_context"
    if artifact.role_hint == "roadmap":
        return "roadmap_context"
    if artifact.role_hint == "requirements":
        return "requirements_context"
    if artifact.path is None:
        return "conversation"
    return "supporting_context"


def _infer_project_name(
    context_documents: list[SpecDocument],
    classification: InputShapeClassification,
) -> str:
    for document in context_documents:
        project_name = document.metadata.get("Proyecto")
        if project_name:
            return project_name.strip("` ")
    for document in context_documents:
        if document.title and document.title != "Preamble":
            cleaned = document.title.strip()
            cleaned = re.sub(r"^(Roadmap|Class Diagram)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
            return cleaned
    if classification.artifacts:
        return Path(classification.artifacts[0].display_name).stem.replace("_", " ").strip()
    return "Proyecto Sintetizado"


def _build_synthesized_requirements_document(
    *,
    project_name: str,
    classification: InputShapeClassification,
    context_documents: list[SpecDocument],
) -> SpecDocument:
    sections = _collect_requirement_sections(context_documents)
    lines = [
        f"# Requerimientos Formales - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        f"**Source Input Kind**: {classification.shape_kind}",
        "",
    ]

    if not sections:
        lines.extend(
            [
                "## Vision del producto",
                "",
                "Normalizar el input recibido hasta un paquete de requerimientos y roadmap certificado.",
                "- Definir alcance funcional",
                "- Definir restricciones tecnicas",
                "- Definir decisiones arquitectonicas iniciales",
            ]
        )
    else:
        for title, summary, bullets in sections:
            lines.extend(["## " + title, ""])
            if summary:
                lines.append(summary)
                lines.append("")
            for bullet in bullets[:10]:
                lines.append(f"- {bullet}")
            lines.append("")

    content = "\n".join(lines).strip() + "\n"
    document = parse_spec_text(
        content,
        doc_type="requirements",
        path=_build_virtual_output_path(classification.artifacts, "requirements.generated.md"),
    )
    return _with_certification_metadata(document, classification=classification)


def _collect_requirement_sections(
    context_documents: list[SpecDocument],
) -> list[tuple[str, str, list[str]]]:
    collected: list[tuple[str, str, list[str]]] = []
    seen_titles: set[str] = set()

    for document in context_documents:
        for section in document.sections:
            if section.heading_level < 2:
                continue
            title_key = section.title.strip().lower()
            if title_key in seen_titles or title_key in EXCLUDED_REQUIREMENTS_TITLES:
                continue
            if title_key.startswith("fase "):
                continue

            summary = summarize_section(section.body)
            bullets = [bullet for bullet in extract_bullets(section.body) if bullet]
            if not summary and not bullets:
                continue

            seen_titles.add(title_key)
            collected.append((section.title.strip(), summary, bullets))

    return collected[:16]


def _build_synthesized_roadmap_document(
    *,
    project_name: str,
    classification: InputShapeClassification,
    context_documents: list[SpecDocument],
) -> SpecDocument:
    epics = _extract_epics_from_context(context_documents)
    if not epics:
        epics = _build_fallback_epics(context_documents)

    lines = [
        f"# Roadmap Sintetizado - {project_name}",
        "",
        f"**Proyecto**: {project_name}",
        f"**Source Input Kind**: {classification.shape_kind}",
        "",
    ]

    ticket_counter = 1
    for epic_index, epic in enumerate(epics, start=1):
        lines.extend(
            [
                f"## EP-{epic_index:03d} · {epic['title']}",
                f"> Objetivo: {epic['objective']}",
                "",
            ]
        )
        for ticket in epic["tickets"]:
            lines.extend(
                [
                    f"### TICKET-{ticket_counter:03d} · {ticket['title']}",
                    "```",
                    "Tipo: feature",
                    f"Prioridad: {ticket['priority']}",
                    f"Est.: {ticket['estimate']}",
                    "Deps.: ninguna",
                    "```",
                    "",
                    "**Descripción**",
                    ticket["description"],
                    "",
                    "**Criterios de aceptación**",
                ]
            )
            for acceptance_item in ticket["acceptance"]:
                lines.append(f"- {acceptance_item}")
            lines.append("")
            ticket_counter += 1

    content = "\n".join(lines).strip() + "\n"
    document = parse_spec_text(
        content,
        doc_type="roadmap",
        path=_build_virtual_output_path(classification.artifacts, "roadmap.generated.md"),
    )
    return _with_certification_metadata(document, classification=classification)


def _extract_epics_from_context(context_documents: list[SpecDocument]) -> list[dict[str, Any]]:
    epics: list[dict[str, Any]] = []

    for document in context_documents:
        for section in document.sections:
            if section.heading_level != 2:
                continue
            phase_match = PHASE_TITLE_PATTERN.match(section.title.strip())
            if not phase_match:
                continue

            objective = _extract_h3_block(section.body, "Objetivo") or summarize_section(section.body)
            changes_block = _extract_h3_block(section.body, "Cambios")
            tickets = _build_tickets_from_changes_block(changes_block)
            if not tickets:
                tickets = _build_tickets_from_bullets(extract_bullets(section.body))
            if not tickets:
                tickets = [
                    {
                        "title": f"Implementar {section.title.strip()}",
                        "description": objective or f"Implementar la fase {section.title.strip()}.",
                        "acceptance": [objective or f"Fase {section.title.strip()} definida e implementada."],
                        "priority": "P1",
                        "estimate": "8 h",
                    }
                ]

            epics.append(
                {
                    "title": section.title.strip(),
                    "objective": objective or f"Ejecutar {section.title.strip()}",
                    "tickets": tickets,
                }
            )

    return epics


def _build_tickets_from_changes_block(changes_block: str) -> list[dict[str, Any]]:
    grouped_bullets = _group_top_level_bullets(changes_block)
    tickets: list[dict[str, Any]] = []

    for group in grouped_bullets:
        title = _clean_ticket_title(group[0])
        nested_items = [line.strip()[2:].strip() for line in group[1:] if line.strip().startswith("- ")]
        description_lines = [line.strip() for line in group[1:] if line.strip() and not line.strip().startswith("- ")]
        description = " ".join(description_lines).strip() or f"Implementar {title.lower()}."
        acceptance = nested_items or [title]
        tickets.append(
            {
                "title": title,
                "description": description,
                "acceptance": acceptance[:10],
                "priority": "P0" if len(tickets) == 0 else "P1",
                "estimate": _estimate_for_ticket(title, nested_items),
            }
        )

    return tickets[:12]


def _build_tickets_from_bullets(bullets: list[str]) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for index, bullet in enumerate(bullets[:8], start=1):
        title = _clean_ticket_title(bullet)
        tickets.append(
            {
                "title": title,
                "description": f"Implementar {title.lower()}.",
                "acceptance": [title],
                "priority": "P0" if index == 1 else "P1",
                "estimate": "6 h",
            }
        )
    return tickets


def _build_fallback_epics(context_documents: list[SpecDocument]) -> list[dict[str, Any]]:
    candidate_sections = _collect_requirement_sections(context_documents)[:6]
    tickets = [
        {
            "title": title,
            "description": summary or f"Formalizar {title.lower()}.",
            "acceptance": bullets[:6] or [title],
            "priority": "P0" if index == 1 else "P1",
            "estimate": _estimate_for_ticket(title, bullets),
        }
        for index, (title, summary, bullets) in enumerate(candidate_sections, start=1)
    ]
    if not tickets:
        tickets = [
            {
                "title": "Discovery y formalizacion",
                "description": "Convertir el brief abierto en requerimientos formales y roadmap ejecutable.",
                "acceptance": [
                    "Se documenta el alcance funcional",
                    "Se documenta la arquitectura inicial",
                    "Se documenta el roadmap inicial",
                ],
                "priority": "P0",
                "estimate": "8 h",
            }
        ]
    return [
        {
            "title": "Discovery y formalizacion inicial",
            "objective": "Cerrar el gap entre el input abierto y el paquete certificado de Mission Control.",
            "tickets": tickets,
        }
    ]


def _extract_h3_block(section_body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^###\s+{re.escape(heading)}\s*$\n+(.*?)(?=^###\s+|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(section_body)
    return match.group(1).strip() if match else ""


def _group_top_level_bullets(markdown_block: str) -> list[list[str]]:
    groups: list[list[str]] = []
    current_group: list[str] = []

    for raw_line in markdown_block.splitlines():
        line = raw_line.rstrip()
        if re.match(r"^- ", line):
            if current_group:
                groups.append(current_group)
            current_group = [line]
            continue
        if current_group and line.strip():
            current_group.append(line)

    if current_group:
        groups.append(current_group)
    return groups


def _clean_ticket_title(value: str) -> str:
    title = value.strip()
    if title.startswith("- "):
        title = title[2:]
    title = title.strip("` ")
    if title.endswith(":"):
        title = title[:-1]
    return title or "Trabajo de implementacion"


def _estimate_for_ticket(title: str, nested_items: list[str]) -> str:
    complexity_score = len(nested_items)
    lowered = title.lower()
    if any(token in lowered for token in ("arquitectura", "foundation", "infraestructura", "migracion")):
        complexity_score += 2
    if complexity_score >= 8:
        return "16 h"
    if complexity_score >= 4:
        return "12 h"
    if complexity_score >= 2:
        return "8 h"
    return "4 h"


def _build_virtual_output_path(artifacts: list[InputArtifact], filename: str) -> str:
    resolved_paths = [artifact.path for artifact in artifacts if artifact.path]
    if not resolved_paths:
        return f"memory://mission-control/generated/{filename}"

    common_root = Path(os.path.commonpath(resolved_paths))
    if common_root.is_file():
        common_root = common_root.parent
    return str((common_root / "__mission_control_generated__" / filename).resolve())


def _looks_like_formal_roadmap(content: str) -> bool:
    return bool(FORMAL_ROADMAP_PATTERN.search(content) or TICKET_PATTERN.search(content))


def _looks_like_phase_roadmap(content: str) -> bool:
    return bool(PHASE_ROADMAP_PATTERN.search(content))
