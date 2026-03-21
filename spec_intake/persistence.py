from __future__ import annotations

import hashlib
import json

from database import (
    BlueprintRequirementRecord,
    DeliveryEpicRecord,
    DeliveryTaskRecord,
    ProjectBlueprintRecord,
    RetrospectiveItemRecord,
    SpecDocumentRecord,
    SpecSectionRecord,
    StageFeedbackRecord,
    db,
)

from .models import ProjectBlueprint, SpecDocument


def hash_spec_document(document: SpecDocument) -> str:
    payload = {
        "doc_type": document.doc_type,
        "path": document.path,
        "title": document.title,
        "metadata": document.metadata,
        "sections": [
            {
                "heading_level": section.heading_level,
                "title": section.title,
                "body": section.body,
            }
            for section in document.sections
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BlueprintPersistenceService:
    """Persists intake outputs into Mission Control's Postgres-backed schema."""

    def persist_blueprint(self, blueprint: ProjectBlueprint) -> ProjectBlueprintRecord:
        document_records: dict[str, SpecDocumentRecord] = {}

        for document in blueprint.source_documents:
            document_record = SpecDocumentRecord(
                project_name=blueprint.project_name,
                doc_type=document.doc_type,
                path=document.path,
                title=document.title,
                metadata_json=document.metadata,
                content_hash=hash_spec_document(document),
            )
            db.session.add(document_record)
            db.session.flush()

            for order_index, section in enumerate(document.sections, start=1):
                db.session.add(
                    SpecSectionRecord(
                        spec_document_id=document_record.id,
                        heading_level=section.heading_level,
                        title=section.title,
                        body=section.body,
                        order_index=order_index,
                    )
                )

            document_records[document.doc_type] = document_record

        blueprint_record = ProjectBlueprintRecord(
            project_name=blueprint.project_name,
            source_requirements_document_id=document_records["requirements"].id,
            source_roadmap_document_id=document_records["roadmap"].id,
            capabilities_json=blueprint.capabilities,
            acceptance_items_json=blueprint.acceptance_items,
            issues_json=blueprint.issues,
        )
        db.session.add(blueprint_record)
        db.session.flush()

        for order_index, requirement in enumerate(blueprint.requirements, start=1):
            db.session.add(
                BlueprintRequirementRecord(
                    project_blueprint_id=blueprint_record.id,
                    requirement_id=requirement.requirement_id,
                    title=requirement.title,
                    source_section=requirement.source_section,
                    category=requirement.category,
                    summary=requirement.summary,
                    constraints_json=requirement.constraints,
                    acceptance_hints_json=requirement.acceptance_hints,
                    order_index=order_index,
                )
            )

        for epic_order, epic in enumerate(blueprint.roadmap_epics, start=1):
            epic_record = DeliveryEpicRecord(
                project_blueprint_id=blueprint_record.id,
                epic_id=epic.epic_id,
                name=epic.name,
                objective=epic.objective,
                order_index=epic_order,
            )
            db.session.add(epic_record)
            db.session.flush()

            for task_order, ticket in enumerate(epic.tickets, start=1):
                db.session.add(
                    DeliveryTaskRecord(
                        delivery_epic_id=epic_record.id,
                        ticket_id=ticket.ticket_id,
                        title=ticket.title,
                        ticket_type=ticket.ticket_type,
                        priority=ticket.priority,
                        estimate=ticket.estimate,
                        dependencies_json=ticket.dependencies,
                        description=ticket.description,
                        acceptance_criteria_json=ticket.acceptance_criteria,
                        order_index=task_order,
                    )
                )

        db.session.commit()
        return blueprint_record

    def list_blueprints(self) -> list[ProjectBlueprintRecord]:
        return ProjectBlueprintRecord.query.order_by(ProjectBlueprintRecord.created_at.desc()).all()

    def get_blueprint(self, blueprint_id: int) -> ProjectBlueprintRecord | None:
        return db.session.get(ProjectBlueprintRecord, blueprint_id)

    def add_stage_feedback(
        self,
        *,
        blueprint_id: int,
        stage_name: str,
        status: str,
        source: str,
        feedback_text: str,
    ) -> StageFeedbackRecord:
        feedback = StageFeedbackRecord(
            project_blueprint_id=blueprint_id,
            stage_name=stage_name,
            status=status,
            source=source,
            feedback_text=feedback_text,
        )
        db.session.add(feedback)
        db.session.commit()
        return feedback

    def add_retrospective_item(
        self,
        *,
        blueprint_id: int,
        category: str,
        summary: str,
        action_item: str | None = None,
        owner: str | None = None,
        status: str = "open",
    ) -> RetrospectiveItemRecord:
        item = RetrospectiveItemRecord(
            project_blueprint_id=blueprint_id,
            category=category,
            summary=summary,
            action_item=action_item,
            owner=owner,
            status=status,
        )
        db.session.add(item)
        db.session.commit()
        return item

    def serialize_blueprint_detail(self, blueprint_record: ProjectBlueprintRecord) -> dict[str, object]:
        requirements = sorted(blueprint_record.requirements, key=lambda item: item.order_index)
        epics = sorted(blueprint_record.delivery_epics, key=lambda item: item.order_index)
        stage_feedback = sorted(
            blueprint_record.stage_feedback,
            key=lambda item: item.created_at.isoformat() if item.created_at else "",
        )
        retrospective_items = sorted(
            blueprint_record.retrospective_items,
            key=lambda item: item.created_at.isoformat() if item.created_at else "",
        )

        return {
            **blueprint_record.to_dict(),
            "source_documents": {
                "requirements": {
                    **blueprint_record.requirements_document.to_dict(),
                    "sections": [
                        section.to_dict()
                        for section in sorted(
                            blueprint_record.requirements_document.sections,
                            key=lambda section: section.order_index,
                        )
                    ],
                },
                "roadmap": {
                    **blueprint_record.roadmap_document.to_dict(),
                    "sections": [
                        section.to_dict()
                        for section in sorted(
                            blueprint_record.roadmap_document.sections,
                            key=lambda section: section.order_index,
                        )
                    ],
                },
            },
            "requirements": [item.to_dict() for item in requirements],
            "roadmap_epics": [
                {
                    **epic.to_dict(),
                    "tickets": [
                        ticket.to_dict()
                        for ticket in sorted(epic.delivery_tasks, key=lambda task: task.order_index)
                    ],
                }
                for epic in epics
            ],
            "stage_feedback": [item.to_dict() for item in stage_feedback],
            "retrospective_items": [item.to_dict() for item in retrospective_items],
            "summary": {
                "requirements_count": len(requirements),
                "epics_count": len(epics),
                "tickets_count": sum(len(epic.delivery_tasks) for epic in epics),
                "feedback_count": len(stage_feedback),
                "retrospective_items_count": len(retrospective_items),
                "issues_count": len(blueprint_record.issues_json or []),
            },
        }
