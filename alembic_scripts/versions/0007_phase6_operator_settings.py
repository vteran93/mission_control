"""Phase 6 operator settings

Revision ID: 0007_phase6_operator_settings
Revises: 0006_phase4_plan_approval_status
Create Date: 2026-03-25 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_phase6_operator_settings"
down_revision = "0006_phase4_plan_approval_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_operator_settings_key"), "operator_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_operator_settings_key"), table_name="operator_settings")
    op.drop_table("operator_settings")
