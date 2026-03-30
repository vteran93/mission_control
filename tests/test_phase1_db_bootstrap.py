import importlib
import sqlite3
import sys
from pathlib import Path
from unittest.mock import Mock

import re


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    if module_name == "app":
        for loaded_module in list(sys.modules):
            if (
                loaded_module.startswith("autonomous_delivery")
                or loaded_module.startswith("autonomous_scrum")
                or loaded_module.startswith("spec_intake")
                or loaded_module.startswith("delivery_tracking")
                or loaded_module.startswith("crew_runtime")
                or loaded_module.startswith("operator_control")
                or loaded_module.startswith("github_operator")
            ):
                sys.modules.pop(loaded_module, None)
    return importlib.import_module(module_name)


def test_run_migrations_uses_database_url_override(tmp_path, monkeypatch):
    db_bootstrap = load_module("db_bootstrap")

    alembic_ini = tmp_path / "alembic.ini"
    alembic_ini.write_text("[alembic]\nscript_location = alembic\n", encoding="utf-8")

    captured = {}

    def fake_upgrade(config, revision):
        captured["url"] = config.get_main_option("sqlalchemy.url")
        captured["revision"] = revision

    monkeypatch.setattr(db_bootstrap.command, "upgrade", fake_upgrade)

    db_bootstrap.run_migrations(
        database_url="postgresql+psycopg://mission_control:secret@db:5432/mission_control",
        alembic_ini_path=alembic_ini,
    )

    assert captured["url"] == "postgresql+psycopg://mission_control:secret@db:5432/mission_control"
    assert captured["revision"] == "head"


def test_initialize_database_runs_migrations_and_seeds(tmp_path, monkeypatch):
    database_path = tmp_path / "instance" / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MISSION_CONTROL_INSTANCE_PATH", str(tmp_path / "instance"))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("MISSION_CONTROL_QUEUE_DIR", str(tmp_path / "runtime" / "queue"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", str(tmp_path / "runtime" / "locks"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", str(tmp_path / "scripts"))

    app_module = load_module("app")
    db_bootstrap = load_module("db_bootstrap")

    app = app_module.create_app()

    run_migrations = Mock()
    seed_initial_agents = Mock()

    db_bootstrap.initialize_database(
        app,
        run_migrations_fn=run_migrations,
        seed_initial_agents_fn=seed_initial_agents,
    )

    run_migrations.assert_called_once()
    seed_initial_agents.assert_called_once()


def test_alembic_revision_ids_fit_default_version_table_width():
    versions_dir = Path(__file__).resolve().parent.parent / "alembic_scripts" / "versions"
    revision_pattern = re.compile(r'^revision = "([^"]+)"$', re.MULTILINE)

    revision_ids = []
    for path in sorted(versions_dir.glob("*.py")):
        revision_match = revision_pattern.search(path.read_text(encoding="utf-8"))
        assert revision_match is not None, f"Missing revision in {path.name}"
        revision_ids.append(revision_match.group(1))

    assert revision_ids
    assert all(len(revision_id) <= 32 for revision_id in revision_ids)


def test_run_migrations_supports_sqlite_backend(tmp_path):
    db_bootstrap = load_module("db_bootstrap")
    sqlite_path = tmp_path / "mission_control.db"
    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"

    db_bootstrap.run_migrations(
        database_url=f"sqlite:///{sqlite_path}",
        alembic_ini_path=alembic_ini,
    )

    with sqlite3.connect(sqlite_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(task_queue)")
        }
        sprint_cycle_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(sprint_cycles)")
        }
        blueprint_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(project_blueprints)")
        }
        foreign_key_targets = {
            row[2]
            for row in connection.execute("PRAGMA foreign_key_list(task_queue)")
        }
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {"project_blueprint_id", "delivery_task_id", "crew_seed", "runtime_metadata_json"} <= columns
    assert "delivery_guardrails_json" in blueprint_columns
    assert "scrum_plan_id" in sprint_cycle_columns
    assert {"project_blueprints", "delivery_tasks"} <= foreign_key_targets
    assert {"scrum_plans", "scrum_plan_items"} <= tables
