import subprocess
import sys
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select


def test_copy_table_data_between_engines(tmp_path):
    from data_migration import copy_table_data

    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    source_engine = create_engine(f"sqlite:///{source_path}")
    target_engine = create_engine(f"sqlite:///{target_path}")

    metadata = MetaData()
    agents = Table(
        "agents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100), nullable=False),
    )
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)

    with source_engine.begin() as connection:
        connection.execute(
            agents.insert(),
            [
                {"id": 1, "name": "Jarvis-Dev"},
                {"id": 2, "name": "Jarvis-QA"},
            ],
        )

    copied_rows = copy_table_data(
        source_engine=source_engine,
        target_engine=target_engine,
        table_name="agents",
    )

    assert copied_rows == 2

    with target_engine.connect() as connection:
        result = connection.execute(select(agents.c.id, agents.c.name).order_by(agents.c.id)).all()

    assert result == [(1, "Jarvis-Dev"), (2, "Jarvis-QA")]


def test_copy_table_data_nulls_orphaned_nullable_foreign_keys(tmp_path):
    from data_migration import copy_table_data

    source_path = tmp_path / "source_fk.db"
    target_path = tmp_path / "target_fk.db"
    source_engine = create_engine(f"sqlite:///{source_path}")
    target_engine = create_engine(f"sqlite:///{target_path}")

    metadata = MetaData()
    tasks = Table(
        "tasks",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String(100), nullable=False),
    )
    messages = Table(
        "messages",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("task_id", Integer, nullable=True),
        Column("from_agent", String(100), nullable=False),
        Column("content", String(200), nullable=False),
    )
    metadata.create_all(source_engine)
    metadata.create_all(target_engine)

    with source_engine.begin() as connection:
        connection.execute(tasks.insert(), [{"id": 1, "title": "Task 1"}])
        connection.execute(
            messages.insert(),
            [
                {"id": 10, "task_id": 1, "from_agent": "Jarvis", "content": "linked"},
                {"id": 11, "task_id": 999, "from_agent": "Jarvis", "content": "orphan"},
            ],
        )

    copied_rows = copy_table_data(
        source_engine=source_engine,
        target_engine=target_engine,
        table_name="messages",
    )

    assert copied_rows == 2

    with target_engine.connect() as connection:
        result = connection.execute(
            select(messages.c.id, messages.c.task_id).order_by(messages.c.id)
        ).all()

    assert result == [(10, 1), (11, None)]


def test_migration_script_can_run_from_repo_root():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/migrate_sqlite_to_postgres.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Copy Mission Control data from SQLite to Postgres." in result.stdout
