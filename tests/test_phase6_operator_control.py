import importlib
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def load_app_stack():
    for module_name in list(sys.modules):
        if (
            module_name in {"app", "config", "database", "operator_control"}
            or module_name.startswith("crew_runtime")
            or module_name.startswith("autonomous_delivery")
            or module_name.startswith("autonomous_scrum")
            or module_name.startswith("spec_intake")
            or module_name.startswith("delivery_tracking")
            or module_name.startswith("github_operator")
        ):
            sys.modules.pop(module_name, None)
    database_module = importlib.import_module("database")
    app_module = importlib.import_module("app")
    return app_module, database_module


@pytest.fixture
def configured_operator_app(tmp_path, monkeypatch):
    instance_dir = tmp_path / "instance"
    runtime_dir = tmp_path / "runtime"
    queue_dir = runtime_dir / "message_queue"
    database_path = instance_dir / "phase6.db"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MISSION_CONTROL_INSTANCE_PATH", str(instance_dir))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("MISSION_CONTROL_QUEUE_DIR", str(queue_dir))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", str(runtime_dir / "locks"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", str(tmp_path / "scripts"))
    monkeypatch.setenv("ENABLE_AGENT_WAKEUPS", "false")
    monkeypatch.setenv("PORT", "5001")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.default:11434")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "qwen-default")
    monkeypatch.setenv("GITHUB_API_URL", "https://github.default/api/v3")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    app_module, database_module = load_app_stack()
    app = app_module.create_app()

    with app.app_context():
        app_module.db.create_all()

    return app, database_module


def import_sample_blueprint(client, tmp_path):
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"
    requirements_path.write_text(
        """# Demo
## Objetivo
- Validar operator dashboard profundo
""",
        encoding="utf-8",
    )
    roadmap_path.write_text(
        """# Roadmap
## EP-1 · Demo

### TICKET-101 · Instrumentar PR timeline
```
Tipo: feature
Prioridad: P1
Est.: 2 h
Deps.: ninguna
```

**Descripción**
Crear trazabilidad GitHub para el blueprint.

**Criterios de aceptación**
- [ ] Existe trazabilidad GitHub
""",
        encoding="utf-8",
    )
    response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    assert response.status_code == 201
    return response.get_json()


def generate_private_key_pem() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_operator_dashboard_updates_settings_and_masks_secrets(
    configured_operator_app,
    monkeypatch,
):
    app, database_module = configured_operator_app
    client = app.test_client()
    providers_module = importlib.import_module("crew_runtime.providers")

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, timeout, headers=None):
        if url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "qwen2.5-coder"}]})
        if url.endswith("/rate_limit"):
            assert headers is not None
            assert headers["Authorization"] == "Bearer ghp-test-token"
            return FakeResponse({"rate": {"remaining": 4999}})
        raise AssertionError(f"Unexpected provider probe: {url}")

    monkeypatch.setattr(providers_module.requests, "get", fake_get)

    response = client.get("/api/operator/dashboard")
    assert response.status_code == 200
    initial_payload = response.get_json()
    assert initial_payload["settings"]["github"]["token_configured"] is False
    assert initial_payload["overview"]["blueprints"] == 0

    update_response = client.put(
        "/api/operator/settings",
        json={
            "ollama": {
                "base_url": "http://ollama.override:11434",
                "default_model": "qwen-override",
            },
            "bedrock": {
                "region": "us-east-1",
                "planner_model": "anthropic.claude-3-7-sonnet",
                "reviewer_model": "anthropic.claude-3-5-sonnet",
            },
            "github": {
                "api_url": "https://github.override/api/v3",
                "repository": "acme/platform",
                "default_base_branch": "main",
                "protected_branches": "main,release",
                "token": "ghp-test-token",
            },
        },
    )
    assert update_response.status_code == 200
    payload = update_response.get_json()

    assert payload["settings"]["ollama"]["base_url"] == "http://ollama.override:11434"
    assert payload["settings"]["ollama"]["default_model"] == "qwen-override"
    assert payload["settings"]["github"]["repository"] == "acme/platform"
    assert payload["settings"]["github"]["protected_branches"] == ["main", "release"]
    assert payload["settings"]["github"]["token_configured"] is True
    assert payload["providers"]["github"]["ok"] is True
    assert payload["providers"]["ollama"]["ok"] is True
    assert payload["runtime_config_applied"] is True

    settings_response = client.get("/api/operator/settings")
    assert settings_response.status_code == 200
    settings_payload = settings_response.get_json()
    assert "token" not in settings_payload["github"]
    assert settings_payload["github"]["token_configured"] is True

    with app.app_context():
        stored = {
            row.key: row
            for row in database_module.OperatorSettingRecord.query.order_by(
                database_module.OperatorSettingRecord.key.asc()
            ).all()
        }
        assert stored["github.token"].is_secret is True
        assert stored["github.protected_branches"].value_json == ["main", "release"]


def test_operator_settings_reject_unknown_fields(configured_operator_app):
    app, _database_module = configured_operator_app
    client = app.test_client()

    response = client.put(
        "/api/operator/settings",
        json={"runtime": {"enabled": False}},
    )

    assert response.status_code == 400
    assert "Unsupported operator settings group" in response.get_json()["error"]


def test_github_app_syncs_branch_protection_and_persists_events(
    configured_operator_app,
    monkeypatch,
):
    app, database_module = configured_operator_app
    client = app.test_client()
    github_module = importlib.import_module("github_operator")

    exchanged_tokens = []
    protection_calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    private_key_pem = generate_private_key_pem()

    def fake_post(url, headers, timeout):
        assert url.endswith("/app/installations/98765/access_tokens")
        bearer = headers["Authorization"].split(" ", 1)[1]
        assert bearer.count(".") == 2
        exchanged_tokens.append(bearer)
        return FakeResponse({"token": "ghs_installation_token", "expires_at": "2030-01-01T00:00:00Z"})

    def fake_put(url, headers, json, timeout):
        protection_calls.append((url, headers, json))
        assert headers["Authorization"] == "Bearer ghs_installation_token"
        return FakeResponse({"url": url, "enforced": True, "rules": json})

    monkeypatch.setattr(github_module.requests, "post", fake_post)
    monkeypatch.setattr(github_module.requests, "put", fake_put)

    response = client.put(
        "/api/operator/settings",
        json={
            "github": {
                "api_url": "https://github.enterprise.local/api/v3",
                "repository": "acme/platform",
                "default_base_branch": "main",
                "protected_branches": ["main", "release"],
                "required_approving_review_count": 2,
                "app_id": 12345,
                "app_installation_id": 98765,
                "app_private_key": private_key_pem,
            }
        },
    )
    assert response.status_code == 200
    assert response.get_json()["settings"]["github"]["auth_mode"] == "app"

    sync_response = client.post("/api/operator/github/sync-branches", json={})
    assert sync_response.status_code == 200
    payload = sync_response.get_json()
    assert payload["auth_mode"] == "app"
    assert payload["branch_count"] == 2
    assert len(exchanged_tokens) == 1
    assert len(protection_calls) == 2
    assert protection_calls[0][2]["required_pull_request_reviews"]["required_approving_review_count"] == 2

    with app.app_context():
        events = database_module.GitHubSyncEventRecord.query.order_by(
            database_module.GitHubSyncEventRecord.id.asc()
        ).all()
        assert len(events) == 2
        assert {event.branch_name for event in events} == {"main", "release"}


def test_github_pull_request_sync_enriches_blueprint_dashboard(
    configured_operator_app,
    monkeypatch,
    tmp_path,
):
    app, database_module = configured_operator_app
    client = app.test_client()
    github_module = importlib.import_module("github_operator")

    blueprint = import_sample_blueprint(client, tmp_path)
    blueprint_id = blueprint["id"]

    client.post(
        f"/api/blueprints/{blueprint_id}/feedback",
        json={
            "stage_name": "review",
            "status": "approved",
            "feedback_text": "Review aprobada para merge.",
        },
    )
    client.post(
        f"/api/blueprints/{blueprint_id}/retrospective-items",
        json={
            "category": "win",
            "summary": "PR visibility funcionando.",
            "action_item": "Mantener sync de PRs.",
        },
    )
    client.post(
        f"/api/blueprints/{blueprint_id}/agent-runs",
        json={
            "agent_name": "github_sync_agent",
            "agent_role": "release",
            "provider": "github",
            "model": "api",
            "status": "completed",
            "input_summary": "Sync pull requests",
            "output_summary": "Pull requests fetched",
            "completed": True,
        },
    )

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, timeout, headers=None, params=None):
        if url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "qwen2.5-coder"}]})
        if url.endswith("/rate_limit"):
            return FakeResponse({"rate": {"remaining": 5000}})
        if url.endswith("/repos/acme/platform/pulls"):
            return FakeResponse(
                [
                    {
                        "number": 17,
                        "title": "Blueprint release candidate",
                        "state": "open",
                        "html_url": "https://github.local/acme/platform/pull/17",
                        "updated_at": "2026-03-25T10:00:00Z",
                        "merged_at": None,
                        "draft": False,
                        "user": {"login": "mission-control"},
                        "head": {"ref": f"mission-control/blueprint-{blueprint_id}-plan-1-rc"},
                        "base": {"ref": "main"},
                    },
                    {
                        "number": 99,
                        "title": "Other repo work",
                        "state": "closed",
                        "html_url": "https://github.local/acme/platform/pull/99",
                        "updated_at": "2026-03-24T10:00:00Z",
                        "merged_at": "2026-03-24T11:00:00Z",
                        "draft": False,
                        "user": {"login": "someone"},
                        "head": {"ref": "feature/misc"},
                        "base": {"ref": "main"},
                    },
                ]
            )
        raise AssertionError(f"Unexpected GitHub request: {url}")

    monkeypatch.setattr(github_module.requests, "get", fake_get)

    response = client.put(
        "/api/operator/settings",
        json={
            "github": {
                "api_url": "https://github.local/api/v3",
                "repository": "acme/platform",
                "default_base_branch": "main",
                "protected_branches": ["main"],
                "token": "ghp-test-token",
            }
        },
    )
    assert response.status_code == 200

    sync_response = client.post(
        "/api/operator/github/pull-requests/sync",
        json={"state": "all", "per_page": 20},
    )
    assert sync_response.status_code == 200
    assert sync_response.get_json()["pull_request_count"] == 2

    timeline_response = client.get("/api/operator/github/timeline?limit=20")
    assert timeline_response.status_code == 200
    assert len(timeline_response.get_json()["events"]) == 2

    dashboard_response = client.get(f"/api/blueprints/{blueprint_id}/operator-dashboard")
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.get_json()
    assert dashboard["report"]["counts"]["github_sync_events"] == 1
    assert dashboard["retrospective_items"][0]["summary"] == "PR visibility funcionando."
    assert dashboard["recent_feedback"][0]["feedback_text"] == "Review aprobada para merge."
    assert dashboard["github"]["pull_requests"][0]["number"] == 17

    with app.app_context():
        blueprint_events = database_module.GitHubSyncEventRecord.query.filter_by(
            project_blueprint_id=blueprint_id
        ).all()
        assert len(blueprint_events) == 1
