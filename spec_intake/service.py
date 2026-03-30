from __future__ import annotations

from pathlib import Path

from .certification import build_certified_input
from .flexible_inputs import build_source_documents_from_artifacts
from .models import ProjectBlueprint
from .parser import parse_requirements, parse_roadmap


class SpecIntakeService:
    """Builds a first-pass blueprint from formal specs or normalized input artifacts."""

    def build_blueprint(
        self,
        *,
        requirements_path: str | Path,
        roadmap_path: str | Path,
    ) -> ProjectBlueprint:
        return self.build_blueprint_from_input_artifacts(
            input_artifacts=[
                {"path": requirements_path, "role": "requirements"},
                {"path": roadmap_path, "role": "roadmap"},
            ]
        )

    def build_blueprint_from_input_artifacts(
        self,
        *,
        input_artifacts: list[object],
    ) -> ProjectBlueprint:
        classification, source_documents = build_source_documents_from_artifacts(input_artifacts)
        requirements_document = next(
            document for document in source_documents if document.doc_type == "requirements"
        )
        roadmap_document = next(document for document in source_documents if document.doc_type == "roadmap")
        requirements = parse_requirements(requirements_document)
        roadmap_epics = parse_roadmap(roadmap_document)

        capabilities = self._build_capabilities(requirements_document, roadmap_epics)
        acceptance_items = self._collect_acceptance_items(roadmap_epics)
        issues = self._detect_issues(requirements_document, roadmap_document, requirements, roadmap_epics)

        project_name = (
            roadmap_document.metadata.get("Proyecto")
            or roadmap_document.title
            or requirements_document.metadata.get("Proyecto")
            or requirements_document.title
        )

        blueprint = ProjectBlueprint(
            project_name=project_name,
            source_documents=source_documents,
            capabilities=capabilities,
            requirements=requirements,
            roadmap_epics=roadmap_epics,
            acceptance_items=acceptance_items,
            issues=issues,
        )
        certified_input = build_certified_input(blueprint, source_input_kind=classification.shape_kind)
        return ProjectBlueprint(
            project_name=blueprint.project_name,
            source_documents=blueprint.source_documents,
            capabilities=blueprint.capabilities,
            requirements=blueprint.requirements,
            roadmap_epics=blueprint.roadmap_epics,
            acceptance_items=blueprint.acceptance_items,
            issues=blueprint.issues,
            certified_input=certified_input,
        )

    def _build_capabilities(self, requirements_document, roadmap_epics) -> list[str]:
        capabilities: list[str] = []
        for section in requirements_document.sections:
            if section.heading_level == 2 and section.title != "Preamble":
                capabilities.append(section.title)
        for epic in roadmap_epics:
            capabilities.append(epic.name)

        deduped: list[str] = []
        seen = set()
        for capability in capabilities:
            normalized = capability.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(capability.strip())
        return deduped

    def _collect_acceptance_items(self, roadmap_epics) -> list[str]:
        acceptance_items: list[str] = []
        for epic in roadmap_epics:
            for ticket in epic.tickets:
                acceptance_items.extend(ticket.acceptance_criteria)
        return acceptance_items

    def _detect_issues(self, requirements_document, roadmap_document, requirements, roadmap_epics) -> list[str]:
        issues: list[str] = []
        if not requirements:
            issues.append("No se detectaron requirement items en el documento de requerimientos.")
        if not roadmap_epics:
            issues.append("No se detectaron epics en el documento de roadmap.")

        ticket_ids = {
            ticket.ticket_id
            for epic in roadmap_epics
            for ticket in epic.tickets
        }
        for epic in roadmap_epics:
            if not epic.tickets:
                issues.append(f"{epic.epic_id} no contiene tickets parseables.")
            for ticket in epic.tickets:
                for dependency in ticket.dependencies:
                    if dependency not in ticket_ids:
                        issues.append(
                            f"{ticket.ticket_id} referencia dependencia desconocida: {dependency}."
                        )

        project_name = roadmap_document.metadata.get("Proyecto")
        if not project_name:
            issues.append("El roadmap no declara metadata **Proyecto**.")

        if requirements_document.title == "Preamble":
            issues.append("No se encontro heading principal en requirements.")

        return issues
