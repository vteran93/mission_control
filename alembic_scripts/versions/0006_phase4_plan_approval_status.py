"""Phase 4 scrum plan approval status

Revision ID: 0006_phase4_plan_approval_status
Revises: 0005_phase4_scrum_planner
Create Date: 2026-03-24 10:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_phase4_plan_approval_status"
down_revision = "0005_phase4_scrum_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scrum_plans",
        sa.Column(
            "approval_status",
            sa.String(length=50),
            nullable=False,
            server_default="approved",
        ),
    )
    op.create_index(
        op.f("ix_scrum_plans_approval_status"),
        "scrum_plans",
        ["approval_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scrum_plans_approval_status"), table_name="scrum_plans")
    op.drop_column("scrum_plans", "approval_status")
