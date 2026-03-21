from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from database import Agent, db


def run_migrations(database_url: str, alembic_ini_path: str | Path) -> None:
    config = Config(str(alembic_ini_path))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def seed_initial_agents() -> None:
    if Agent.query.count() > 0:
        return

    db.session.add_all(
        [
            Agent(name="Jarvis-Dev", role="dev", status="idle"),
            Agent(name="Jarvis-QA", role="qa", status="idle"),
        ]
    )
    db.session.commit()


def initialize_database(
    app,
    run_migrations_fn=run_migrations,
    seed_initial_agents_fn=seed_initial_agents,
) -> None:
    Path(app.config["MISSION_CONTROL_INSTANCE_PATH"]).mkdir(parents=True, exist_ok=True)
    run_migrations_fn(
        database_url=app.config["SQLALCHEMY_DATABASE_URI"],
        alembic_ini_path=app.config["ALEMBIC_INI_PATH"],
    )
    with app.app_context():
        seed_initial_agents_fn()
