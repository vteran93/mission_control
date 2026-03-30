"""Phase 6 blueprint delivery guardrails

Revision ID: 0009_phase6_blueprint_guardrails
Revises: 0008_phase6_github_sync_events
Create Date: 2026-03-30 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_phase6_blueprint_guardrails"
down_revision = "0008_phase6_github_sync_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_blueprints",
        sa.Column("delivery_guardrails_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_blueprints", "delivery_guardrails_json")
