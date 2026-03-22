from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case

from database import Message, TaskQueue, db


PRIORITY_ORDER = {
    "urgent": 0,
    "high": 1,
    "normal": 2,
    "low": 3,
}


def normalize_priority(raw_priority: str | None) -> str:
    if not raw_priority:
        return "normal"
    lowered = raw_priority.strip().lower()
    return lowered if lowered in PRIORITY_ORDER else "normal"


class DatabaseQueueDispatcher:
    """DB-backed dispatch queue used by the runtime and compatibility APIs."""

    def enqueue_message(
        self,
        *,
        message: Message,
        target_agent: str,
        content: str | None = None,
        priority: str = "normal",
        project_blueprint_id: int | None = None,
        delivery_task_id: int | None = None,
        crew_seed: str | None = None,
    ) -> TaskQueue:
        existing_entry = (
            TaskQueue.query.filter_by(message_id=message.id, target_agent=target_agent)
            .order_by(TaskQueue.id.desc())
            .first()
        )
        if existing_entry and existing_entry.status in {"pending", "processing"}:
            return existing_entry

        queue_entry = TaskQueue(
            target_agent=target_agent,
            message_id=message.id,
            project_blueprint_id=project_blueprint_id,
            delivery_task_id=delivery_task_id,
            from_agent=message.from_agent,
            content=content or message.content,
            priority=normalize_priority(priority),
            crew_seed=crew_seed,
            status="pending",
        )
        db.session.add(queue_entry)
        db.session.commit()
        return queue_entry

    def create_message_and_enqueue(
        self,
        *,
        target_agent: str,
        message_content: str,
        from_agent: str,
        task_id: int | None = None,
        priority: str = "normal",
        project_blueprint_id: int | None = None,
        delivery_task_id: int | None = None,
        crew_seed: str | None = None,
    ) -> tuple[Message, TaskQueue]:
        message = Message(
            task_id=task_id,
            from_agent=from_agent,
            content=f"📤 → {target_agent}: {message_content}",
        )
        db.session.add(message)
        db.session.flush()

        queue_entry = TaskQueue(
            target_agent=target_agent,
            message_id=message.id,
            project_blueprint_id=project_blueprint_id,
            delivery_task_id=delivery_task_id,
            from_agent=from_agent,
            content=message_content,
            priority=normalize_priority(priority),
            crew_seed=crew_seed,
            status="pending",
        )
        db.session.add(queue_entry)
        db.session.commit()
        return message, queue_entry

    def list_entries(
        self,
        *,
        limit: int = 100,
        statuses: tuple[str, ...] | None = None,
    ) -> list[TaskQueue]:
        query = TaskQueue.query
        if statuses:
            query = query.filter(TaskQueue.status.in_(statuses))
        return query.order_by(TaskQueue.created_at.desc()).limit(limit).all()

    def delete_entry(self, queue_entry_id: int) -> bool:
        queue_entry = db.session.get(TaskQueue, queue_entry_id)
        if queue_entry is None:
            return False
        db.session.delete(queue_entry)
        db.session.commit()
        return True

    def claim_pending_entries(
        self,
        *,
        limit: int = 1,
        target_agent: str | None = None,
        queue_entry_id: int | None = None,
    ) -> list[TaskQueue]:
        priority_rank = case(PRIORITY_ORDER, value=TaskQueue.priority, else_=99)
        query = TaskQueue.query.filter_by(status="pending")
        if target_agent:
            query = query.filter_by(target_agent=target_agent)
        if queue_entry_id is not None:
            query = query.filter_by(id=queue_entry_id)
        bind = db.session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)

        queue_entries = (
            query.order_by(priority_rank.asc(), TaskQueue.created_at.asc()).limit(limit).all()
        )
        for queue_entry in queue_entries:
            queue_entry.status = "processing"
            queue_entry.started_at = datetime.now(UTC)
        if queue_entries:
            db.session.flush()
            db.session.commit()
        return queue_entries

    def recover_abandoned_entries(
        self,
        *,
        stale_after_seconds: float,
        target_agent: str | None = None,
    ) -> list[TaskQueue]:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        query = TaskQueue.query.filter(
            TaskQueue.status == "processing",
            TaskQueue.started_at.isnot(None),
            TaskQueue.started_at < cutoff,
        )
        if target_agent:
            query = query.filter_by(target_agent=target_agent)

        queue_entries = query.order_by(TaskQueue.started_at.asc()).all()
        for queue_entry in queue_entries:
            queue_entry.status = "pending"
            queue_entry.started_at = None
            queue_entry.retry_count = (queue_entry.retry_count or 0) + 1
            queue_entry.error_message = (
                f"Recovered abandoned processing entry after exceeding {int(stale_after_seconds)} seconds"
            )

        if queue_entries:
            db.session.commit()
        return queue_entries

    def queue_summary(self, *, stale_after_seconds: float | None = None) -> dict[str, int]:
        summary = {
            "pending": TaskQueue.query.filter_by(status="pending").count(),
            "processing": TaskQueue.query.filter_by(status="processing").count(),
            "completed": TaskQueue.query.filter_by(status="completed").count(),
            "failed": TaskQueue.query.filter_by(status="failed").count(),
        }
        if stale_after_seconds is not None:
            cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
            summary["stale_processing"] = (
                TaskQueue.query.filter(
                    TaskQueue.status == "processing",
                    TaskQueue.started_at.isnot(None),
                    TaskQueue.started_at < cutoff,
                ).count()
            )
        return summary

    def apply_result(
        self,
        queue_entry: TaskQueue,
        *,
        success: bool,
        detail: str,
        runtime_session_key: str | None = None,
        runtime_metadata: dict | None = None,
    ) -> TaskQueue:
        queue_entry.status = "completed" if success else "failed"
        queue_entry.completed_at = datetime.now(UTC)
        queue_entry.error_message = None if success else detail
        queue_entry.clawdbot_session_key = runtime_session_key
        queue_entry.runtime_metadata_json = runtime_metadata or {}
        db.session.commit()
        return queue_entry

    @staticmethod
    def serialize(queue_entry: TaskQueue) -> dict[str, object]:
        payload = queue_entry.to_dict()
        payload["message"] = queue_entry.content
        payload["task_id"] = queue_entry.message.task_id if queue_entry.message else None
        payload["message_id"] = str(queue_entry.id)
        return payload
