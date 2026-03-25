import importlib
import sys
import types
from datetime import datetime, timedelta, timezone


def clear_runtime_modules():
    for module_name in list(sys.modules):
        if (
            module_name in {"app", "config", "database"}
            or module_name.startswith("autonomous_delivery")
            or module_name.startswith("autonomous_scrum")
            or module_name.startswith("crew_runtime")
            or module_name.startswith("spec_intake")
            or module_name.startswith("delivery_tracking")
            or module_name.startswith("operator_control")
            or module_name.startswith("github_operator")
        ):
            sys.modules.pop(module_name, None)


def install_fake_crewai(monkeypatch):
    fake_crewai = types.ModuleType("crewai")

    class FakeLLM:
        instances = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            FakeLLM.instances.append(self)

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeTask:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeCrew:
        last_kwargs = None
        kickoff_plan = []
        kickoff_history = []

        def __init__(self, **kwargs):
            FakeCrew.last_kwargs = kwargs
            self.kwargs = kwargs

        def kickoff(self):
            FakeCrew.kickoff_history.append(self.kwargs)
            if FakeCrew.kickoff_plan:
                next_item = FakeCrew.kickoff_plan.pop(0)
                if isinstance(next_item, Exception):
                    raise next_item
                return next_item
            return types.SimpleNamespace(raw="fake crew output")

    class FakeProcess:
        hierarchical = "hierarchical"

    fake_crewai.Agent = FakeAgent
    fake_crewai.Crew = FakeCrew
    fake_crewai.Task = FakeTask
    fake_crewai.Process = FakeProcess
    fake_crewai.LLM = FakeLLM

    monkeypatch.setitem(sys.modules, "crewai", fake_crewai)
    return fake_crewai, FakeCrew, FakeLLM


def build_phase3_app(tmp_path, monkeypatch):
    clear_runtime_modules()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'instance' / 'phase3.db'}")
    monkeypatch.setenv("MISSION_CONTROL_INSTANCE_PATH", str(tmp_path / "instance"))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("MISSION_CONTROL_QUEUE_DIR", str(tmp_path / "runtime" / "queue"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", str(tmp_path / "runtime" / "locks"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", str(tmp_path / "scripts"))
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_EXECUTOR", "crewai")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_AUTOSTART", "false")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_RECOVER_AFTER_SECONDS", "60")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_ESCALATE_AFTER_RETRIES", "1")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_ENABLE_FALLBACK", "true")
    monkeypatch.setenv("MISSION_CONTROL_LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("MISSION_CONTROL_LLM_MAX_TOKENS", "2048")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:latest")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("BEDROCK_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_PLANNER_MODEL", "anthropic.claude-3-7-sonnet")
    monkeypatch.setenv("BEDROCK_REVIEWER_MODEL", "anthropic.claude-3-5-sonnet")

    app_module = importlib.import_module("app")
    crewai_executor_module = importlib.import_module("crew_runtime.crewai_executor")
    providers_module = importlib.import_module("crew_runtime.providers")

    monkeypatch.setattr(
        crewai_executor_module.importlib.util,
        "find_spec",
        lambda name: object() if name == "crewai" else None,
    )
    monkeypatch.setattr(
        providers_module.importlib.util,
        "find_spec",
        lambda name: object() if name in {"crewai", "boto3"} else None,
    )

    app = app_module.create_app()
    with app.app_context():
        app_module.db.create_all()
    return app, app_module


def import_minimal_blueprint(client, tmp_path):
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"

    requirements_path.write_text(
        """# Mission Control Runtime
## Alcance
- Debe ejecutar crews con CrewAI
- Debe registrar telemetry en Postgres
""",
        encoding="utf-8",
    )
    roadmap_path.write_text(
        """# Roadmap
**Proyecto**: Mission Control Runtime

## EP-3 · Runtime
### TICKET-301 · Conectar dispatch
```
Tipo: feature
Prioridad: P0
Est.: 4 h
Deps.: ninguna
```

**Descripción**
Conectar dispatch al runtime agentic.

**Criterios de aceptación**
- [ ] Ejecuta crew
- [ ] Persiste telemetry
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


def test_model_registry_routes_dev_to_ollama_and_pm_to_bedrock(tmp_path, monkeypatch):
    install_fake_crewai(monkeypatch)
    app, _ = build_phase3_app(tmp_path, monkeypatch)
    client = app.test_client()

    runtime = app.extensions["mission_control_runtime"]
    registry_payload = runtime.model_registry.describe()
    response = client.get("/api/runtime/model-profiles")

    assert response.status_code == 200
    assert response.get_json()["routing_defaults"]["jarvis-dev"] == "worker_local"
    assert registry_payload["routing_defaults"]["jarvis-dev"] == "worker_local"
    assert registry_payload["routing_defaults"]["jarvis-pm"] == "planner_bedrock"
    assert registry_payload["routing_defaults"]["jarvis-qa"] == "reviewer_bedrock"
    assert registry_payload["escalation_defaults"]["jarvis-dev"] == [
        "worker_local",
        "reviewer_bedrock",
    ]
    assert registry_payload["profiles"]["worker_local"]["model"] == "ollama/qwen2.5-coder:latest"
    assert registry_payload["profiles"]["worker_local"]["timeout_seconds"] == 45
    assert registry_payload["runtime_policy"]["escalate_after_retries"] == 1


def test_runtime_exposes_tools_and_crew_seeds(tmp_path, monkeypatch):
    install_fake_crewai(monkeypatch)
    app, _ = build_phase3_app(tmp_path, monkeypatch)
    client = app.test_client()

    tools_response = client.get("/api/runtime/tools")
    seeds_response = client.get("/api/runtime/crew-seeds")
    health_response = client.get("/api/runtime/health")

    assert tools_response.status_code == 200
    tools_payload = tools_response.get_json()
    tool_names = {item["name"] for item in tools_payload}
    assert "workspace_write_file" in tool_names
    assert "workspace_run_unix_command" in tool_names
    assert "workspace_run_mypy" in tool_names
    assert "workspace_package_manager_context" in tool_names
    assert "mission_control_execution_report" in tool_names
    assert "mission_control_scrum_plan_context" in tool_names
    assert "mission_control_sprint_readiness_view" in tool_names

    assert seeds_response.status_code == 200
    seeds_payload = seeds_response.get_json()
    assert set(seeds_payload) == {"intake", "planning", "scrum_planning", "delivery", "review", "retro"}
    assert seeds_payload["intake"]["tool_groups"] == ["mission_control", "workspace_context"]
    assert seeds_payload["scrum_planning"]["role"] == "Scrum Planning Lead"
    assert seeds_payload["retro"]["role"] == "Retrospective Facilitator"

    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    assert health_payload["toolkit"]["tool_count"] >= 11
    assert "retro" in health_payload["toolkit"]["crew_seeds"]


def test_runtime_dispatch_executes_crewai_seed_and_persists_output(tmp_path, monkeypatch):
    _, fake_crew_class, fake_llm_class = install_fake_crewai(monkeypatch)
    app, app_module = build_phase3_app(tmp_path, monkeypatch)
    client = app.test_client()

    queue_response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "jarvis-dev", "message": "Implementa un cambio minimo"},
    )
    assert queue_response.status_code == 200
    queue_entry_id = queue_response.get_json()["queue_entry_id"]

    runtime_dispatch_response = client.post(
        "/api/runtime/dispatch",
        json={"queue_entry_id": queue_entry_id},
    )

    assert runtime_dispatch_response.status_code == 200
    payload = runtime_dispatch_response.get_json()
    assert payload["dispatch_ready"] is True
    assert payload["dispatched_count"] == 1
    assert payload["results"][0]["success"] is True
    assert payload["results"][0]["runtime_name"] == "crewai"
    assert payload["results"][0]["external_ref"] == "worker_local"
    assert payload["results"][0]["provider"] == "ollama"
    assert payload["results"][0]["model"] == "ollama/qwen2.5-coder:latest"
    assert payload["results"][0]["attempts"] == 1
    assert payload["results"][0]["fallback_used"] is False
    assert payload["results"][0]["runtime_metadata"]["crew_seed"] == "delivery"
    assert payload["results"][0]["runtime_metadata"]["tool_count"] >= 5

    with app.app_context():
        queue_entry = app_module.TaskQueue.query.one()
        assert queue_entry.status == "completed"
        assert queue_entry.completed_at is not None
        assert queue_entry.runtime_metadata_json["crew_seed"] == "delivery"
        assert app_module.Message.query.count() == 2
        output_message = (
            app_module.Message.query.order_by(app_module.Message.id.desc()).first()
        )
        assert output_message.from_agent == "Jarvis-Dev"
        assert output_message.content == "fake crew output"
        latest_log = app_module.DaemonLog.query.order_by(app_module.DaemonLog.id.desc()).first()
        assert latest_log.agent_name == "dev"
        assert "worker_local" in latest_log.message

    assert fake_crew_class.last_kwargs is not None
    assert fake_crew_class.last_kwargs["process"] == "hierarchical"
    assert fake_crew_class.last_kwargs["name"] == "delivery"
    assert fake_crew_class.last_kwargs["manager_llm"].kwargs["model"] == "ollama/qwen2.5-coder:latest"
    assert fake_llm_class.instances[-1].kwargs["timeout"] == 45
    assert fake_llm_class.instances[-1].kwargs["max_tokens"] == 2048
    agent_tools = fake_crew_class.last_kwargs["agents"][0].kwargs["tools"]
    assert {tool.name for tool in agent_tools} >= {
        "workspace_write_file",
        "workspace_run_unix_command",
        "workspace_run_mypy",
    }


def test_runtime_dispatch_falls_back_to_bedrock_profile_after_local_failure(tmp_path, monkeypatch):
    _, fake_crew_class, _ = install_fake_crewai(monkeypatch)
    fake_crew_class.kickoff_plan = [
        RuntimeError("ollama timeout"),
        types.SimpleNamespace(raw="bedrock recovery output"),
    ]
    app, app_module = build_phase3_app(tmp_path, monkeypatch)
    client = app.test_client()

    queue_response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "jarvis-dev", "message": "Resuelve un bloqueo"},
    )
    queue_entry_id = queue_response.get_json()["queue_entry_id"]

    runtime_dispatch_response = client.post(
        "/api/runtime/dispatch",
        json={"queue_entry_id": queue_entry_id},
    )

    assert runtime_dispatch_response.status_code == 200
    payload = runtime_dispatch_response.get_json()
    assert payload["results"][0]["success"] is True
    assert payload["results"][0]["external_ref"] == "reviewer_bedrock"
    assert payload["results"][0]["provider"] == "bedrock"
    assert payload["results"][0]["fallback_used"] is True
    assert payload["results"][0]["attempts"] == 2

    with app.app_context():
        queue_entry = app_module.db.session.get(app_module.TaskQueue, queue_entry_id)
        assert queue_entry.status == "completed"
        warning_log = (
            app_module.DaemonLog.query.filter_by(level="WARNING")
            .order_by(app_module.DaemonLog.id.desc())
            .first()
        )
        assert warning_log is not None
        assert "worker_local" in warning_log.message
        success_log = (
            app_module.DaemonLog.query.filter_by(level="INFO")
            .order_by(app_module.DaemonLog.id.desc())
            .first()
        )
        assert "reviewer_bedrock" in success_log.message


def test_runtime_dispatch_persists_canonical_tracking_records(tmp_path, monkeypatch):
    _, fake_crew_class, _ = install_fake_crewai(monkeypatch)
    app, app_module = build_phase3_app(tmp_path, monkeypatch)
    client = app.test_client()

    blueprint = import_minimal_blueprint(client, tmp_path)
    blueprint_id = blueprint["id"]
    delivery_task_id = blueprint["roadmap_epics"][0]["tickets"][0]["id"]

    queue_response = client.post(
        "/api/send-agent-message",
        json={
            "target_agent": "jarvis-pm",
            "message": "Analiza el blueprint y prepara siguiente paso.",
            "project_blueprint_id": blueprint_id,
            "delivery_task_id": delivery_task_id,
            "crew_seed": "intake",
        },
    )
    assert queue_response.status_code == 200
    queue_entry_id = queue_response.get_json()["queue_entry_id"]

    dispatch_response = client.post(
        "/api/runtime/dispatch",
        json={"queue_entry_id": queue_entry_id},
    )

    assert dispatch_response.status_code == 200
    payload = dispatch_response.get_json()
    assert payload["results"][0]["success"] is True
    assert payload["results"][0]["runtime_metadata"]["crew_seed"] == "intake"

    with app.app_context():
        database_module = importlib.import_module("database")
        queue_entry = app_module.db.session.get(app_module.TaskQueue, queue_entry_id)
        assert queue_entry.project_blueprint_id == blueprint_id
        assert queue_entry.delivery_task_id == delivery_task_id
        assert queue_entry.crew_seed == "intake"
        assert queue_entry.runtime_metadata_json["agent_run_id"] is not None
        assert queue_entry.runtime_metadata_json["task_execution_id"] is not None

        agent_run = database_module.AgentRunRecord.query.one()
        assert agent_run.project_blueprint_id == blueprint_id
        assert agent_run.status == "completed"
        assert agent_run.runtime_name == "crewai"
        assert agent_run.provider == "bedrock"

        task_execution = database_module.TaskExecutionRecord.query.one()
        assert task_execution.delivery_task_id == delivery_task_id
        assert task_execution.status == "done"

        invocation = database_module.LLMInvocationRecord.query.one()
        assert invocation.project_blueprint_id == blueprint_id
        assert invocation.purpose == "intake"
        assert invocation.status == "completed"
        assert invocation.metadata_json["attempt_number"] == 1

    assert fake_crew_class.last_kwargs["name"] == "intake"


def test_runtime_dispatch_supports_retro_seed_override(tmp_path, monkeypatch):
    _, fake_crew_class, _ = install_fake_crewai(monkeypatch)
    app, _ = build_phase3_app(tmp_path, monkeypatch)
    client = app.test_client()

    queue_response = client.post(
        "/api/send-agent-message",
        json={
            "target_agent": "jarvis-pm",
            "message": "Genera retrospective del sprint.",
            "crew_seed": "retro",
        },
    )

    dispatch_response = client.post(
        "/api/runtime/dispatch",
        json={"queue_entry_id": queue_response.get_json()["queue_entry_id"]},
    )

    assert dispatch_response.status_code == 200
    payload = dispatch_response.get_json()
    assert payload["results"][0]["runtime_metadata"]["crew_seed"] == "retro"
    assert fake_crew_class.last_kwargs["name"] == "retro"


def test_runtime_recover_queue_requeues_abandoned_processing_entries(tmp_path, monkeypatch):
    install_fake_crewai(monkeypatch)
    app, app_module = build_phase3_app(tmp_path, monkeypatch)
    client = app.test_client()

    queue_response = client.post(
        "/api/send-agent-message",
        json={"target_agent": "jarvis-qa", "message": "Revisa un item abandonado"},
    )
    queue_entry_id = queue_response.get_json()["queue_entry_id"]

    with app.app_context():
        queue_entry = app_module.db.session.get(app_module.TaskQueue, queue_entry_id)
        queue_entry.status = "processing"
        queue_entry.started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        app_module.db.session.commit()

    recover_response = client.post("/api/runtime/recover-queue", json={"stale_after_seconds": 60})

    assert recover_response.status_code == 200
    payload = recover_response.get_json()
    assert payload["recovered_count"] == 1
    assert payload["recovered_entries"][0]["id"] == queue_entry_id

    with app.app_context():
        queue_entry = app_module.db.session.get(app_module.TaskQueue, queue_entry_id)
        assert queue_entry.status == "pending"
        assert queue_entry.started_at is None
        assert queue_entry.retry_count == 1
        assert "Recovered abandoned processing entry" in queue_entry.error_message
