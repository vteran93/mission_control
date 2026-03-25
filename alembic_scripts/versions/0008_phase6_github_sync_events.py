"""Phase 6 GitHub sync events

Revision ID: 0008_phase6_github_sync_events
Revises: 0007_phase6_operator_settings
Create Date: 2026-03-25 12:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_phase6_github_sync_events"
down_revision = "0007_phase6_operator_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_sync_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=True),
        sa.Column("repository", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("pull_request_number", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_github_sync_events_project_blueprint_id"), "github_sync_events", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_github_sync_events_repository"), "github_sync_events", ["repository"], unique=False)
    op.create_index(op.f("ix_github_sync_events_event_type"), "github_sync_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_github_sync_events_status"), "github_sync_events", ["status"], unique=False)
    op.create_index(op.f("ix_github_sync_events_branch_name"), "github_sync_events", ["branch_name"], unique=False)
    op.create_index(op.f("ix_github_sync_events_pull_request_number"), "github_sync_events", ["pull_request_number"], unique=False)
    op.create_index(op.f("ix_github_sync_events_external_id"), "github_sync_events", ["external_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_github_sync_events_external_id"), table_name="github_sync_events")
    op.drop_index(op.f("ix_github_sync_events_pull_request_number"), table_name="github_sync_events")
    op.drop_index(op.f("ix_github_sync_events_branch_name"), table_name="github_sync_events")
    op.drop_index(op.f("ix_github_sync_events_status"), table_name="github_sync_events")
    op.drop_index(op.f("ix_github_sync_events_event_type"), table_name="github_sync_events")
    op.drop_index(op.f("ix_github_sync_events_repository"), table_name="github_sync_events")
    op.drop_index(op.f("ix_github_sync_events_project_blueprint_id"), table_name="github_sync_events")
    op.drop_table("github_sync_events")
