from __future__ import annotations

from typing import Iterable

from sqlalchemy import MetaData, create_engine, inspect, text

from database import db

LEGACY_NULLABLE_FOREIGN_KEYS = {
    "documents": [("task_id", "tasks", "id")],
    "messages": [("task_id", "tasks", "id")],
    "notifications": [("agent_id", "agents", "id")],
    "tasks": [("project_id", "projects", "id"), ("sprint_id", "sprints", "id")],
}


def default_table_names() -> list[str]:
    return [table.name for table in db.metadata.sorted_tables]


def copy_table_data(source_engine, target_engine, table_name: str) -> int:
    source_metadata = MetaData()
    target_metadata = MetaData()
    source_metadata.reflect(bind=source_engine, only=[table_name])
    target_metadata.reflect(bind=target_engine, only=[table_name])

    source_table = source_metadata.tables[table_name]
    target_table = target_metadata.tables[table_name]

    with source_engine.connect() as source_connection:
        rows = [dict(row._mapping) for row in source_connection.execute(source_table.select())]

    if not rows:
        return 0

    rows = sanitize_legacy_rows(source_engine, table_name, rows)

    with target_engine.begin() as target_connection:
        target_connection.execute(target_table.insert(), rows)

    sync_postgres_sequence(target_engine, table_name, target_table)
    return len(rows)


def copy_all_tables(source_engine, target_engine, table_names: Iterable[str]) -> dict[str, int]:
    source_table_names = set(inspect(source_engine).get_table_names())
    copied = {}
    for table_name in table_names:
        if table_name not in source_table_names:
            copied[table_name] = 0
            continue
        copied[table_name] = copy_table_data(source_engine, target_engine, table_name)
    return copied


def table_row_count(engine, table_name: str) -> int:
    with engine.connect() as connection:
        return connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()


def assert_tables_empty(engine, table_names: Iterable[str]) -> None:
    non_empty_tables = [
        table_name for table_name in table_names if table_row_count(engine, table_name) > 0
    ]
    if non_empty_tables:
        joined = ", ".join(non_empty_tables)
        raise RuntimeError(f"Target database is not empty for tables: {joined}")


def sanitize_legacy_rows(source_engine, table_name: str, rows: list[dict]) -> list[dict]:
    foreign_keys = LEGACY_NULLABLE_FOREIGN_KEYS.get(table_name, [])
    if not foreign_keys:
        return rows

    sanitized_rows = [row.copy() for row in rows]
    for column_name, referenced_table, referenced_column in foreign_keys:
        valid_reference_ids = load_reference_ids(source_engine, referenced_table, referenced_column)
        for row in sanitized_rows:
            reference_value = row.get(column_name)
            if reference_value is None:
                continue
            if reference_value not in valid_reference_ids:
                row[column_name] = None
    return sanitized_rows


def load_reference_ids(source_engine, table_name: str, column_name: str) -> set[int]:
    statement = text(f'SELECT "{column_name}" FROM "{table_name}"')
    with source_engine.connect() as connection:
        return {row[0] for row in connection.execute(statement)}


def sync_postgres_sequence(engine, table_name: str, reflected_table) -> None:
    if engine.dialect.name != "postgresql":
        return

    primary_keys = list(reflected_table.primary_key.columns)
    if len(primary_keys) != 1:
        return

    primary_key = primary_keys[0]
    if primary_key.type.python_type is not int:
        return

    quoted_table = f'"{table_name}"'
    quoted_column = f'"{primary_key.name}"'
    statement = text(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table_name}', '{primary_key.name}'),
            COALESCE((SELECT MAX({quoted_column}) FROM {quoted_table}), 1),
            COALESCE((SELECT COUNT(*) > 0 FROM {quoted_table}), false)
        )
        """
    )
    with engine.begin() as connection:
        connection.execute(statement)


def build_engine(database_url: str):
    return create_engine(database_url)
