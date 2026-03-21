from __future__ import annotations

from pathlib import Path

from .models import ProjectBlueprint
from .parser import parse_requirements, parse_roadmap, parse_spec_document


class SpecIntakeService:
    """Builds a first-pass blueprint from requirements and roadmap documents."""

    def build_blueprint(
        self,
        *,
        requirements_path: str | Path,
        roadmap_path: str | Path,
    ) -> ProjectBlueprint:
        requirements_document = parse_spec_document(requirements_path, doc_type="requirements")
        roadmap_document = parse_spec_document(roadmap_path, doc_type="roadmap")

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

        return ProjectBlueprint(
            project_name=project_name,
            source_documents=[requirements_document, roadmap_document],
            capabilities=capabilities,
            requirements=requirements,
            roadmap_epics=roadmap_epics,
            acceptance_items=acceptance_items,
            issues=issues,
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
