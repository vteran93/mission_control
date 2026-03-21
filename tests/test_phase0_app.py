import importlib
import json
import sys
from pathlib import Path

import pytest


def load_app_module():
    sys.modules.pop("app", None)
    return importlib.import_module("app")


@pytest.fixture
def configured_app(tmp_path, monkeypatch):
    instance_dir = tmp_path / "instance"
    runtime_dir = tmp_path / "runtime"
    queue_dir = runtime_dir / "message_queue"
    scripts_dir = tmp_path / "scripts"
    database_path = instance_dir / "test.db"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MISSION_CONTROL_INSTANCE_PATH", str(instance_dir))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("MISSION_CONTROL_QUEUE_DIR", str(queue_dir))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", str(runtime_dir / "locks"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", str(scripts_dir))
    monkeypatch.setenv("ENABLE_AGENT_WAKEUPS", "false")
    monkeypatch.setenv("PORT", "5001")

    app_module = load_app_module()
    app = app_module.create_app()

    with app.app_context():
        app_module.db.create_all()

    yield app, app_module, queue_dir


def test_create_app_reads_environment_configuration(configured_app):
    app, _, queue_dir = configured_app

    assert app.config["SQLALCHEMY_DATABASE_URI"].endswith("test.db")
    assert app.config["MISSION_CONTROL_QUEUE_DIR"] == str(queue_dir)
    assert app.config["ENABLE_AGENT_WAKEUPS"] is False
    assert app.config["PORT"] == 5001


def test_health_endpoint_reports_ok(configured_app):
    app, _, _ = configured_app
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_send_agent_message_writes_to_configured_queue(configured_app):
    app, app_module, queue_dir = configured_app
    client = app.test_client()

    response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "jarvis-dev", "message": "Implementa el ticket"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "queued"

    queued_files = list(queue_dir.glob("*.json"))
    assert len(queued_files) == 1

    queued_payload = json.loads(queued_files[0].read_text(encoding="utf-8"))
    assert queued_payload["target_agent"] == "jarvis-dev"
    assert queued_payload["message"] == "Implementa el ticket"

    with app.app_context():
        assert app_module.Message.query.count() == 1


def test_send_agent_message_rejects_unknown_agent(configured_app):
    app, _, queue_dir = configured_app
    client = app.test_client()

    response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "all", "message": "Broadcast no soportado"},
    )

    assert response.status_code == 400
    assert queue_dir.exists() is False or list(queue_dir.iterdir()) == []
