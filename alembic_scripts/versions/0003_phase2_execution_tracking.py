"""Phase 2 execution tracking

Revision ID: 0003_phase2_execution_tracking
Revises: 0002_phase2_delivery_model
Create Date: 2026-03-21 22:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_phase2_execution_tracking"
down_revision = "0002_phase2_delivery_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sprint_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sprint_cycles_project_blueprint_id"), "sprint_cycles", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_sprint_cycles_status"), "sprint_cycles", ["status"], unique=False)
    op.create_index(op.f("ix_sprint_cycles_created_at"), "sprint_cycles", ["created_at"], unique=False)

    op.create_table(
        "sprint_stage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sprint_stage_events_project_blueprint_id"), "sprint_stage_events", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_sprint_stage_events_stage_name"), "sprint_stage_events", ["stage_name"], unique=False)
    op.create_index(op.f("ix_sprint_stage_events_status"), "sprint_stage_events", ["status"], unique=False)
    op.create_index(op.f("ix_sprint_stage_events_created_at"), "sprint_stage_events", ["created_at"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("agent_role", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("runtime_name", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_project_blueprint_id"), "agent_runs", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_agent_name"), "agent_runs", ["agent_name"], unique=False)
    op.create_index(op.f("ix_agent_runs_agent_role"), "agent_runs", ["agent_role"], unique=False)
    op.create_index(op.f("ix_agent_runs_provider"), "agent_runs", ["provider"], unique=False)
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)
    op.create_index(op.f("ix_agent_runs_started_at"), "agent_runs", ["started_at"], unique=False)

    op.create_table(
        "task_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("delivery_task_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["delivery_task_id"], ["delivery_tasks.id"]),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_executions_project_blueprint_id"), "task_executions", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_task_executions_delivery_task_id"), "task_executions", ["delivery_task_id"], unique=False)
    op.create_index(op.f("ix_task_executions_agent_run_id"), "task_executions", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_task_executions_status"), "task_executions", ["status"], unique=False)
    op.create_index(op.f("ix_task_executions_started_at"), "task_executions", ["started_at"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("task_execution_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("uri", sa.String(length=1000), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artifacts_project_blueprint_id"), "artifacts", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_artifacts_agent_run_id"), "artifacts", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_artifacts_task_execution_id"), "artifacts", ["task_execution_id"], unique=False)
    op.create_index(op.f("ix_artifacts_document_id"), "artifacts", ["document_id"], unique=False)
    op.create_index(op.f("ix_artifacts_artifact_type"), "artifacts", ["artifact_type"], unique=False)
    op.create_index(op.f("ix_artifacts_created_at"), "artifacts", ["created_at"], unique=False)

    op.create_table(
        "handoffs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("task_execution_id", sa.Integer(), nullable=True),
        sa.Column("from_agent", sa.String(length=100), nullable=False),
        sa.Column("to_agent", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_handoffs_project_blueprint_id"), "handoffs", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_handoffs_task_execution_id"), "handoffs", ["task_execution_id"], unique=False)
    op.create_index(op.f("ix_handoffs_from_agent"), "handoffs", ["from_agent"], unique=False)
    op.create_index(op.f("ix_handoffs_to_agent"), "handoffs", ["to_agent"], unique=False)
    op.create_index(op.f("ix_handoffs_status"), "handoffs", ["status"], unique=False)
    op.create_index(op.f("ix_handoffs_created_at"), "handoffs", ["created_at"], unique=False)

    op.create_table(
        "llm_invocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_blueprint_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["project_blueprint_id"], ["project_blueprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_invocations_project_blueprint_id"), "llm_invocations", ["project_blueprint_id"], unique=False)
    op.create_index(op.f("ix_llm_invocations_agent_run_id"), "llm_invocations", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_llm_invocations_provider"), "llm_invocations", ["provider"], unique=False)
    op.create_index(op.f("ix_llm_invocations_model"), "llm_invocations", ["model"], unique=False)
    op.create_index(op.f("ix_llm_invocations_status"), "llm_invocations", ["status"], unique=False)
    op.create_index(op.f("ix_llm_invocations_created_at"), "llm_invocations", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sprint_cycles_created_at"), table_name="sprint_cycles")
    op.drop_index(op.f("ix_sprint_cycles_status"), table_name="sprint_cycles")
    op.drop_index(op.f("ix_sprint_cycles_project_blueprint_id"), table_name="sprint_cycles")
    op.drop_table("sprint_cycles")

    op.drop_index(op.f("ix_llm_invocations_created_at"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_status"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_model"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_provider"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_agent_run_id"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_project_blueprint_id"), table_name="llm_invocations")
    op.drop_table("llm_invocations")

    op.drop_index(op.f("ix_handoffs_created_at"), table_name="handoffs")
    op.drop_index(op.f("ix_handoffs_status"), table_name="handoffs")
    op.drop_index(op.f("ix_handoffs_to_agent"), table_name="handoffs")
    op.drop_index(op.f("ix_handoffs_from_agent"), table_name="handoffs")
    op.drop_index(op.f("ix_handoffs_task_execution_id"), table_name="handoffs")
    op.drop_index(op.f("ix_handoffs_project_blueprint_id"), table_name="handoffs")
    op.drop_table("handoffs")

    op.drop_index(op.f("ix_artifacts_created_at"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_artifact_type"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_document_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_task_execution_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_agent_run_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_project_blueprint_id"), table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index(op.f("ix_task_executions_started_at"), table_name="task_executions")
    op.drop_index(op.f("ix_task_executions_status"), table_name="task_executions")
    op.drop_index(op.f("ix_task_executions_agent_run_id"), table_name="task_executions")
    op.drop_index(op.f("ix_task_executions_delivery_task_id"), table_name="task_executions")
    op.drop_index(op.f("ix_task_executions_project_blueprint_id"), table_name="task_executions")
    op.drop_table("task_executions")

    op.drop_index(op.f("ix_agent_runs_started_at"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_provider"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_role"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_name"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_project_blueprint_id"), table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index(op.f("ix_sprint_stage_events_created_at"), table_name="sprint_stage_events")
    op.drop_index(op.f("ix_sprint_stage_events_status"), table_name="sprint_stage_events")
    op.drop_index(op.f("ix_sprint_stage_events_stage_name"), table_name="sprint_stage_events")
    op.drop_index(op.f("ix_sprint_stage_events_project_blueprint_id"), table_name="sprint_stage_events")
    op.drop_table("sprint_stage_events")
