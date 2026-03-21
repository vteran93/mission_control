"""Phase 2 blueprint delivery model

Revision ID: 0002_phase2_delivery_model
Revises: 0001_initial_schema
Create Date: 2026-03-21 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_phase2_delivery_model"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spec_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spec_documents_project_name"), "spec_documents", ["project_name"], unique=False)
    op.create_index(op.f("ix_spec_documents_doc_type"), "spec_documents", ["doc_type"], unique=False)
    op.create_index(op.f("ix_spec_documents_content_hash"), "spec_documents", ["content_hash"], unique=False)

    op.create_table(
        "spec_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spec_document_id", sa.Integer(), nullable=False),
        sa.Column("heading_level", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["spec_document_id"], ["spec_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spec_sections_spec_document_id"), "spec_sections", ["spec_document_id"], unique=False)

    op.create_table(
        "project_blueprints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("source_requirements_document_id", sa.Integer(), nullable=False),
        sa.Column("source_roadmap_document_id", sa.Integer(), nullable=False),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("acceptance_items_json", sa.JSON(), nullable=True),
        sa.Column("issues_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_requirements_document_id"], ["spec_documents.id"]),
        sa.ForeignKeyConstraint(["source_roadmap_document_id"], ["spec_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_blueprints_project_name"), "project_blueprints", ["project_name"], unique=False)
    op.create_index(op.f("ix_project_blueprints_created_at"), "project_blueprints", ["created_at"], unique=False)

    op.create_table(
        "blueprint_requirements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_section", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("constraints_json", sa.JSON(), nullable=True),
        sa.Column("acceptance_hints_json", sa.JSON(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_blueprint_requirements_project_blueprint_id"), "blueprint_requirements", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_blueprint_requirements_category"), "blueprint_requirements", ["category"], unique=False)

    op.create_table(
        "delivery_epics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("epic_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delivery_epics_project_blueprint_id"), "delivery_epics", ["project_blueprint_id"], unique=False)

    op.create_table(
        "delivery_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("delivery_epic_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("ticket_type", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=True),
        sa.Column("estimate", sa.String(length=50), nullable=True),
        sa.Column("dependencies_json", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria_json", sa.JSON(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["delivery_epic_id"], ["delivery_epics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delivery_tasks_delivery_epic_id"), "delivery_tasks", ["delivery_epic_id"], unique=False)
    op.create_index(op.f("ix_delivery_tasks_ticket_id"), "delivery_tasks", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_delivery_tasks_priority"), "delivery_tasks", ["priority"], unique=False)

    op.create_table(
        "stage_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stage_feedback_project_blueprint_id"), "stage_feedback", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_stage_feedback_stage_name"), "stage_feedback", ["stage_name"], unique=False)
    op.create_index(op.f("ix_stage_feedback_created_at"), "stage_feedback", ["created_at"], unique=False)

    op.create_table(
        "retrospective_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("action_item", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_retrospective_items_project_blueprint_id"), "retrospective_items", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_retrospective_items_category"), "retrospective_items", ["category"], unique=False)
    op.create_index(op.f("ix_retrospective_items_created_at"), "retrospective_items", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_retrospective_items_created_at"), table_name="retrospective_items")
    op.drop_index(op.f("ix_retrospective_items_category"), table_name="retrospective_items")
    op.drop_index(op.f("ix_retrospective_items_project_blueprint_id"), table_name="retrospective_items")
    op.drop_table("retrospective_items")

    op.drop_index(op.f("ix_stage_feedback_created_at"), table_name="stage_feedback")
    op.drop_index(op.f("ix_stage_feedback_stage_name"), table_name="stage_feedback")
    op.drop_index(op.f("ix_stage_feedback_project_blueprint_id"), table_name="stage_feedback")
    op.drop_table("stage_feedback")

    op.drop_index(op.f("ix_delivery_tasks_priority"), table_name="delivery_tasks")
    op.drop_index(op.f("ix_delivery_tasks_ticket_id"), table_name="delivery_tasks")
    op.drop_index(op.f("ix_delivery_tasks_delivery_epic_id"), table_name="delivery_tasks")
    op.drop_table("delivery_tasks")

    op.drop_index(op.f("ix_delivery_epics_project_blueprint_id"), table_name="delivery_epics")
    op.drop_table("delivery_epics")

    op.drop_index(op.f("ix_blueprint_requirements_category"), table_name="blueprint_requirements")
    op.drop_index(op.f("ix_blueprint_requirements_project_blueprint_id"), table_name="blueprint_requirements")
    op.drop_table("blueprint_requirements")

    op.drop_index(op.f("ix_project_blueprints_created_at"), table_name="project_blueprints")
    op.drop_index(op.f("ix_project_blueprints_project_name"), table_name="project_blueprints")
    op.drop_table("project_blueprints")

    op.drop_index(op.f("ix_spec_sections_spec_document_id"), table_name="spec_sections")
    op.drop_table("spec_sections")

    op.drop_index(op.f("ix_spec_documents_content_hash"), table_name="spec_documents")
    op.drop_index(op.f("ix_spec_documents_doc_type"), table_name="spec_documents")
    op.drop_index(op.f("ix_spec_documents_project_name"), table_name="spec_documents")
    op.drop_table("spec_documents")
