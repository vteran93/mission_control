"""Phase 3 runtime context and telemetry

Revision ID: 0004_phase3_runtime_ctx
Revises: 0003_phase2_execution_tracking
Create Date: 2026-03-22 01:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_phase3_runtime_ctx"
down_revision = "0003_phase2_execution_tracking"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("task_queue", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("project_blueprint_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("delivery_task_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("crew_seed", sa.String(length=50), nullable=True))
            batch_op.add_column(sa.Column("runtime_metadata_json", sa.JSON(), nullable=True))
            batch_op.create_index(
                op.f("ix_task_queue_project_blueprint_id"),
                ["project_blueprint_id"],
                unique=False,
            )
            batch_op.create_index(
                op.f("ix_task_queue_delivery_task_id"),
                ["delivery_task_id"],
                unique=False,
            )
            batch_op.create_index(op.f("ix_task_queue_crew_seed"), ["crew_seed"], unique=False)
            batch_op.create_foreign_key(
                "fk_task_queue_project_blueprint_id",
                "project_blueprints",
                ["project_blueprint_id"],
                ["id"],
            )
            batch_op.create_foreign_key(
                "fk_task_queue_delivery_task_id",
                "delivery_tasks",
                ["delivery_task_id"],
                ["id"],
            )
        return

    op.add_column("task_queue", sa.Column("project_blueprint_id", sa.Integer(), nullable=True))
    op.add_column("task_queue", sa.Column("delivery_task_id", sa.Integer(), nullable=True))
    op.add_column("task_queue", sa.Column("crew_seed", sa.String(length=50), nullable=True))
    op.add_column("task_queue", sa.Column("runtime_metadata_json", sa.JSON(), nullable=True))

    op.create_index(
        op.f("ix_task_queue_project_blueprint_id"),
        "task_queue",
        ["project_blueprint_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_queue_delivery_task_id"),
        "task_queue",
        ["delivery_task_id"],
        unique=False,
    )
    op.create_index(op.f("ix_task_queue_crew_seed"), "task_queue", ["crew_seed"], unique=False)

    op.create_foreign_key(
        "fk_task_queue_project_blueprint_id",
        "task_queue",
        "project_blueprints",
        ["project_blueprint_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_task_queue_delivery_task_id",
        "task_queue",
        "delivery_tasks",
        ["delivery_task_id"],
        ["id"],
    )


def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("task_queue", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_task_queue_delivery_task_id", type_="foreignkey")
            batch_op.drop_constraint("fk_task_queue_project_blueprint_id", type_="foreignkey")
            batch_op.drop_index(op.f("ix_task_queue_crew_seed"))
            batch_op.drop_index(op.f("ix_task_queue_delivery_task_id"))
            batch_op.drop_index(op.f("ix_task_queue_project_blueprint_id"))
            batch_op.drop_column("runtime_metadata_json")
            batch_op.drop_column("crew_seed")
            batch_op.drop_column("delivery_task_id")
            batch_op.drop_column("project_blueprint_id")
        return

    op.drop_constraint("fk_task_queue_delivery_task_id", "task_queue", type_="foreignkey")
    op.drop_constraint("fk_task_queue_project_blueprint_id", "task_queue", type_="foreignkey")
    op.drop_index(op.f("ix_task_queue_crew_seed"), table_name="task_queue")
    op.drop_index(op.f("ix_task_queue_delivery_task_id"), table_name="task_queue")
    op.drop_index(op.f("ix_task_queue_project_blueprint_id"), table_name="task_queue")
    op.drop_column("task_queue", "runtime_metadata_json")
    op.drop_column("task_queue", "crew_seed")
    op.drop_column("task_queue", "delivery_task_id")
    op.drop_column("task_queue", "project_blueprint_id")
