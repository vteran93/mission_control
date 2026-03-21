import importlib
import sys
from pathlib import Path
from unittest.mock import Mock


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
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
