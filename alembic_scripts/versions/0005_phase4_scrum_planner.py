"""Phase 4 autonomous scrum planner

Revision ID: 0005_phase4_scrum_planner
Revises: 0004_phase3_runtime_ctx
Create Date: 2026-03-23 08:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_phase4_scrum_planner"
down_revision = "0004_phase3_runtime_ctx"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    op.create_table(
        "scrum_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("planning_mode", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("sprint_capacity", sa.Integer(), nullable=False),
        sa.Column("sprint_length_days", sa.Integer(), nullable=False),
        sa.Column("velocity_factor", sa.Float(), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("escalation_trigger", sa.String(length=100), nullable=False),
        sa.Column("replan_reason", sa.Text(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_blueprint_id", "version", name="uq_scrum_plans_blueprint_version"),
    )
    op.create_index(op.f("ix_scrum_plans_project_blueprint_id"), "scrum_plans", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_scrum_plans_status"), "scrum_plans", ["status"], unique=False)
    op.create_index(op.f("ix_scrum_plans_planning_mode"), "scrum_plans", ["planning_mode"], unique=False)
    op.create_index(op.f("ix_scrum_plans_risk_level"), "scrum_plans", ["risk_level"], unique=False)
    op.create_index(op.f("ix_scrum_plans_escalation_trigger"), "scrum_plans", ["escalation_trigger"], unique=False)
    op.create_index(op.f("ix_scrum_plans_created_at"), "scrum_plans", ["created_at"], unique=False)

    if _is_sqlite():
        with op.batch_alter_table("sprint_cycles", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("scrum_plan_id", sa.Integer(), nullable=True))
            batch_op.create_index(op.f("ix_sprint_cycles_scrum_plan_id"), ["scrum_plan_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_sprint_cycles_scrum_plan_id",
                "scrum_plans",
                ["scrum_plan_id"],
                ["id"],
            )
    else:
        op.add_column("sprint_cycles", sa.Column("scrum_plan_id", sa.Integer(), nullable=True))
        op.create_index(
            op.f("ix_sprint_cycles_scrum_plan_id"),
            "sprint_cycles",
            ["scrum_plan_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_sprint_cycles_scrum_plan_id",
            "sprint_cycles",
            "scrum_plans",
            ["scrum_plan_id"],
            ["id"],
        )

    op.create_table(
        "scrum_plan_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scrum_plan_id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("delivery_task_id", sa.Integer(), nullable=False),
        sa.Column("sprint_cycle_id", sa.Integer(), nullable=True),
        sa.Column("plan_status", sa.String(length=50), nullable=False),
        sa.Column("readiness_status", sa.String(length=50), nullable=False),
        sa.Column("assignee_role", sa.String(length=50), nullable=True),
        sa.Column("sprint_order", sa.Integer(), nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("dependency_depth", sa.Integer(), nullable=False),
        sa.Column("story_points", sa.Integer(), nullable=False),
        sa.Column("capacity_cost", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("depends_on_json", sa.JSON(), nullable=True),
        sa.Column("blocked_by_json", sa.JSON(), nullable=True),
        sa.Column("definition_of_ready_json", sa.JSON(), nullable=True),
        sa.Column("definition_of_done_json", sa.JSON(), nullable=True),
        sa.Column("planning_notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["delivery_task_id"], ["delivery_tasks.id"]),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.ForeignKeyConstraint(["scrum_plan_id"], ["scrum_plans.id"]),
        sa.ForeignKeyConstraint(["sprint_cycle_id"], ["sprint_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scrum_plan_id", "delivery_task_id", name="uq_scrum_plan_items_plan_task"),
    )
    op.create_index(op.f("ix_scrum_plan_items_scrum_plan_id"), "scrum_plan_items", ["scrum_plan_id"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_project_blueprint_id"), "scrum_plan_items", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_delivery_task_id"), "scrum_plan_items", ["delivery_task_id"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_sprint_cycle_id"), "scrum_plan_items", ["sprint_cycle_id"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_plan_status"), "scrum_plan_items", ["plan_status"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_readiness_status"), "scrum_plan_items", ["readiness_status"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_assignee_role"), "scrum_plan_items", ["assignee_role"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_risk_level"), "scrum_plan_items", ["risk_level"], unique=False)
    op.create_index(op.f("ix_scrum_plan_items_created_at"), "scrum_plan_items", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scrum_plan_items_created_at"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_risk_level"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_assignee_role"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_readiness_status"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_plan_status"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_sprint_cycle_id"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_delivery_task_id"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_project_blueprint_id"), table_name="scrum_plan_items")
    op.drop_index(op.f("ix_scrum_plan_items_scrum_plan_id"), table_name="scrum_plan_items")
    op.drop_table("scrum_plan_items")

    if _is_sqlite():
        with op.batch_alter_table("sprint_cycles", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_sprint_cycles_scrum_plan_id", type_="foreignkey")
            batch_op.drop_index(op.f("ix_sprint_cycles_scrum_plan_id"))
            batch_op.drop_column("scrum_plan_id")
    else:
        op.drop_constraint("fk_sprint_cycles_scrum_plan_id", "sprint_cycles", type_="foreignkey")
        op.drop_index(op.f("ix_sprint_cycles_scrum_plan_id"), table_name="sprint_cycles")
        op.drop_column("sprint_cycles", "scrum_plan_id")

    op.drop_index(op.f("ix_scrum_plans_created_at"), table_name="scrum_plans")
    op.drop_index(op.f("ix_scrum_plans_escalation_trigger"), table_name="scrum_plans")
    op.drop_index(op.f("ix_scrum_plans_risk_level"), table_name="scrum_plans")
    op.drop_index(op.f("ix_scrum_plans_planning_mode"), table_name="scrum_plans")
    op.drop_index(op.f("ix_scrum_plans_status"), table_name="scrum_plans")
    op.drop_index(op.f("ix_scrum_plans_project_blueprint_id"), table_name="scrum_plans")
    op.drop_table("scrum_plans")
