data_migration.py
Comment on lines +17 to +18
def default_table_names() -> list[str]:
    return [table.name for table in db.metadata.sorted_tables]
@chatgpt-codex-connector
chatgpt-codex-connector bot
8 minutes ago
P1 Badge Skip tables that do not exist in legacy SQLite sources

default_table_names() now enumerates every model in the current ORM, including the new Phase 2 tables, and copy_all_tables() feeds each of them into copy_table_data(). For any SQLite database created before this commit, source_metadata.reflect(..., only=[table_name]) will hit tables like spec_documents/agent_runs that do not exist yet and abort the migration instead of copying the legacy data. This breaks the advertised SQLite→Postgres upgrade path for pre-Phase-2 deployments.

Useful? React with 👍 / 👎.


---

crew_runtime/dispatcher.py
Comment on lines +115 to +122
        queue_entries = (
            query.order_by(priority_rank.asc(), TaskQueue.created_at.asc()).limit(limit).all()
        )
        for queue_entry in queue_entries:
            queue_entry.status = "processing"
            queue_entry.started_at = datetime.now(UTC)
        if queue_entries:
            db.session.commit()
@chatgpt-codex-connector
chatgpt-codex-connector bot
9 minutes ago
P1 Badge Lock pending queue rows before marking them processing

claim_pending_entries() reads pending rows with a plain SELECT and only changes their status to processing afterwards in Python. If two dispatchers poll at the same time—for example, two app replicas or the background thread plus a manual /api/runtime/dispatch call—they can both read the same pending entries and dispatch the same task twice before either commit lands. The queue needs an atomic claim step (FOR UPDATE SKIP LOCKED/equivalent) to avoid duplicate agent work.

Useful? React with 👍 / 👎.


----


app.py
Comment on lines +57 to +58
    register_routes(app)
    runtime.start_background_dispatcher(app)
@chatgpt-codex-connector
chatgpt-codex-connector bot
9 minutes ago
P1 Badge Start the background dispatcher only after DB bootstrap

When MISSION_CONTROL_DISPATCHER_AUTOSTART=true and a non-disabled executor is configured, create_app() launches the dispatcher thread before init_db(app) runs in the module footer. The first poll path goes straight into TaskQueue.query, so on a fresh install the thread can hit missing tables before Alembic has created them, raise an OperationalError, and never come back up. This makes the new autostart mode fail exactly on first boot.

Useful? React with 👍 / 👎.

----


delivery_tracking/service.py
Comment on lines +146 to +147
        if completed:
            run.completed_at = run.started_at
@chatgpt-codex-connector
chatgpt-codex-connector bot
9 minutes ago
P2 Badge Set completion timestamps after insert defaults are populated

In create_agent_run() the completed path copies run.started_at into completed_at before the row has been inserted. SQLAlchemy does not populate the started_at column default until flush/insert time, so completed_at is persisted as NULL whenever callers pass completed=true. The identical pattern in create_task_execution() means completed runs/executions lose their finish time, which degrades the new timeline/reporting data.

Useful? React with 👍 / 👎.

