"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-20 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("session_key", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "daemon_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_daemon_logs_agent_name"), "daemon_logs", ["agent_name"], unique=False)
    op.create_index(op.f("ix_daemon_logs_timestamp"), "daemon_logs", ["timestamp"], unique=False)
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("repository_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "sprints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("delivered", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("sprint_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("assignee_agent_ids", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("from_agent", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attachments", sa.Text(), nullable=True),
        sa.Column("visible", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_agent", sa.String(length=50), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("from_agent", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("clawdbot_session_key", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_queue_message_id"), "task_queue", ["message_id"], unique=False)
    op.create_index(op.f("ix_task_queue_status"), "task_queue", ["status"], unique=False)
    op.create_index(op.f("ix_task_queue_target_agent"), "task_queue", ["target_agent"], unique=False)
    op.create_index("ix_task_queue_priority_created_at", "task_queue", ["priority", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_queue_priority_created_at", table_name="task_queue")
    op.drop_index(op.f("ix_task_queue_target_agent"), table_name="task_queue")
    op.drop_index(op.f("ix_task_queue_status"), table_name="task_queue")
    op.drop_index(op.f("ix_task_queue_message_id"), table_name="task_queue")
    op.drop_table("task_queue")
    op.drop_table("messages")
    op.drop_table("documents")
    op.drop_table("tasks")
    op.drop_table("notifications")
    op.drop_table("sprints")
    op.drop_table("projects")
    op.drop_index(op.f("ix_daemon_logs_timestamp"), table_name="daemon_logs")
    op.drop_index(op.f("ix_daemon_logs_agent_name"), table_name="daemon_logs")
    op.drop_table("daemon_logs")
    op.drop_table("agents")
