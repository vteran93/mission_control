import importlib
import sys
from unittest.mock import Mock

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
    assert app.config["MISSION_CONTROL_RUNTIME_ENABLED"] is True
    assert app.config["PORT"] == 5001


def test_health_endpoint_reports_ok(configured_app):
    app, _, _ = configured_app
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["agentic_runtime_enabled"] is True


def test_send_agent_message_writes_to_database_queue(configured_app):
    app, app_module, _ = configured_app
    client = app.test_client()

    response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "jarvis-dev", "message": "Implementa el ticket"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "queued"
    assert payload["queue_entry_id"] >= 1

    with app.app_context():
        assert app_module.Message.query.count() == 1
        assert app_module.TaskQueue.query.count() == 1
        queue_entry = app_module.TaskQueue.query.one()
        assert queue_entry.target_agent == "jarvis-dev"
        assert queue_entry.content == "Implementa el ticket"
        assert queue_entry.status == "pending"


def test_send_agent_message_rejects_unknown_agent(configured_app):
    app, app_module, _ = configured_app
    client = app.test_client()

    response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "all", "message": "Broadcast no soportado"},
    )

    assert response.status_code == 400
    with app.app_context():
        assert app_module.TaskQueue.query.count() == 0


def test_message_queue_endpoint_reads_from_database_queue(configured_app):
    app, _, _ = configured_app
    client = app.test_client()

    queue_response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "jarvis-dev", "message": "Implementa el ticket"},
    )
    queue_entry_id = queue_response.get_json()["queue_entry_id"]

    response = client.get("/api/message-queue")

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload) == 1
    assert payload[0]["message_id"] == str(queue_entry_id)
    assert payload[0]["target_agent"] == "jarvis-dev"
    assert payload[0]["message"] == "Implementa el ticket"


def test_posting_message_with_agent_mention_enqueues_dispatch_task(configured_app):
    app, app_module, _ = configured_app
    client = app.test_client()

    response = client.post(
        "/api/messages",
        json={"from_agent": "Victor", "content": "@jarvis-dev toma este ticket"},
    )

    assert response.status_code == 201
    with app.app_context():
        assert app_module.Message.query.count() == 1
        assert app_module.TaskQueue.query.count() == 1
        queue_entry = app_module.TaskQueue.query.one()
        assert queue_entry.target_agent == "jarvis-dev"
        assert queue_entry.content == "@jarvis-dev toma este ticket"


def test_runtime_health_endpoint_reports_provider_status(configured_app, monkeypatch):
    app, _, _ = configured_app
    client = app.test_client()

    import crew_runtime.providers as providers

    def fake_get(url, headers=None, timeout=None):
        response = Mock()
        response.raise_for_status = Mock()
        if url.endswith("/api/tags"):
            response.json.return_value = {"models": [{"name": "qwen2.5-coder:latest"}]}
            return response
        if url.endswith("/rate_limit"):
            response.json.return_value = {}
            return response
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(providers.requests, "get", fake_get)

    response = client.get("/api/runtime/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["runtime"]["enabled"] is True
    assert payload["runtime"]["dispatch_ready"] is False
    assert payload["providers"]["ollama"]["ok"] is True


def test_runtime_dispatch_endpoint_is_disabled_without_executor(configured_app):
    app, _, _ = configured_app
    client = app.test_client()

    response = client.post("/api/runtime/dispatch", json={"limit": 1})

    assert response.status_code == 409
    assert response.get_json()["dispatch_ready"] is False
