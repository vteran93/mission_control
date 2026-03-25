import importlib
import sys

import pytest


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def load_app_stack():
    for module_name in list(sys.modules):
        if (
            module_name == "app"
            or module_name == "database"
            or module_name.startswith("autonomous_delivery")
            or module_name.startswith("autonomous_scrum")
            or module_name.startswith("spec_intake")
            or module_name.startswith("delivery_tracking")
        ):
            sys.modules.pop(module_name, None)
    database_module = importlib.import_module("database")
    app_module = importlib.import_module("app")
    return app_module, database_module


@pytest.fixture
def configured_app_with_specs(tmp_path, monkeypatch):
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"
    database_path = tmp_path / "instance" / "test.db"

    requirements_path.write_text(
        """# Plataforma de Automatizacion
**Framework**: CrewAI

## Arquitectura
La solucion debe correr sobre CrewAI y registrar todo en Postgres.
- Debe usar CrewAI
- Debe usar Postgres

### Intake Agent
Lee documentos de especificacion y los normaliza.
- Debe leer Markdown
- Debe detectar requerimientos
""",
        encoding="utf-8",
    )

    roadmap_path.write_text(
        """# Roadmap
**Proyecto**: Plataforma de Automatizacion

## EP-0 · Setup
> Objetivo: dejar el sistema listo para intake.

### TICKET-001 · Preparar parser base
```
Tipo: feature
Prioridad: P0
Est.: 4 h
Deps.: ninguna
```

**Descripción**
Implementar parser de requerimientos.

**Criterios de aceptación**
- [ ] Parsea Markdown
- [ ] Devuelve blueprint
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MISSION_CONTROL_INSTANCE_PATH", str(tmp_path / "instance"))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("MISSION_CONTROL_QUEUE_DIR", str(tmp_path / "runtime" / "queue"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", str(tmp_path / "runtime" / "locks"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", str(tmp_path / "scripts"))

    app_module, database_module = load_app_stack()
    app = app_module.create_app()

    with app.app_context():
        app_module.db.create_all()

    return app, database_module, requirements_path, roadmap_path


def test_import_blueprint_persists_records(configured_app_with_specs):
    app, database_module, requirements_path, roadmap_path = configured_app_with_specs
    client = app.test_client()

    response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["project_name"] == "Plataforma de Automatizacion"
    assert payload["summary"]["tickets_count"] == 1
    assert payload["summary"]["requirements_count"] >= 2

    list_response = client.get("/api/blueprints")
    assert list_response.status_code == 200
    assert len(list_response.get_json()) == 1

    with app.app_context():
        assert database_module.SpecDocumentRecord.query.count() == 2
        assert database_module.SpecSectionRecord.query.count() >= 4
        assert database_module.ProjectBlueprintRecord.query.count() == 1
        assert database_module.BlueprintRequirementRecord.query.count() >= 2
        assert database_module.DeliveryEpicRecord.query.count() == 1
        assert database_module.DeliveryTaskRecord.query.count() == 1


def test_blueprint_feedback_and_retrospective_are_persisted(configured_app_with_specs):
    app, _, requirements_path, roadmap_path = configured_app_with_specs
    client = app.test_client()

    import_response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    blueprint_id = import_response.get_json()["id"]

    feedback_response = client.post(
        f"/api/blueprints/{blueprint_id}/feedback",
        json={
            "stage_name": "planning",
            "status": "approved",
            "source": "qa",
            "feedback_text": "El intake tiene suficiente estructura para persistirse.",
        },
    )
    assert feedback_response.status_code == 201

    retro_response = client.post(
        f"/api/blueprints/{blueprint_id}/retrospective-items",
        json={
            "category": "process",
            "summary": "Persistir timeline por blueprint",
            "action_item": "Agregar agent_runs en el siguiente slice",
            "owner": "Jarvis-PM",
        },
    )
    assert retro_response.status_code == 201

    detail_response = client.get(f"/api/blueprints/{blueprint_id}")
    assert detail_response.status_code == 200
    payload = detail_response.get_json()
    assert len(payload["stage_feedback"]) == 1
    assert len(payload["retrospective_items"]) == 1
    assert payload["stage_feedback"][0]["stage_name"] == "planning"
    assert payload["retrospective_items"][0]["owner"] == "Jarvis-PM"


def test_execution_tracking_endpoints_build_timeline_and_report(configured_app_with_specs):
    app, _, requirements_path, roadmap_path = configured_app_with_specs
    client = app.test_client()

    import_response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    blueprint = import_response.get_json()
    blueprint_id = blueprint["id"]
    delivery_task_id = blueprint["roadmap_epics"][0]["tickets"][0]["id"]

    sprint_cycle = client.post(
        f"/api/blueprints/{blueprint_id}/sprint-cycles",
        json={
            "name": "Sprint 1",
            "goal": "Tener intake y persistencia operativos",
            "capacity": 8,
            "status": "active",
            "start_date": "2026-03-21T09:00:00",
            "end_date": "2026-03-28T18:00:00",
            "metadata": {"cadence": "weekly"},
        },
    )
    assert sprint_cycle.status_code == 201

    sprint_list = client.get(f"/api/blueprints/{blueprint_id}/sprint-cycles")
    assert sprint_list.status_code == 200
    assert len(sprint_list.get_json()) == 1

    stage_event = client.post(
        f"/api/blueprints/{blueprint_id}/stage-events",
        json={
            "stage_name": "planning",
            "status": "completed",
            "source": "Jarvis-PM",
            "summary": "Sprint planning generado",
            "metadata": {"sprint": "Sprint 1"},
        },
    )
    assert stage_event.status_code == 201

    agent_run = client.post(
        f"/api/blueprints/{blueprint_id}/agent-runs",
        json={
            "agent_name": "Jarvis-Dev",
            "agent_role": "dev",
            "provider": "ollama",
            "model": "qwen2.5-coder:latest",
            "status": "completed",
            "input_summary": "Implementar parser base",
            "output_summary": "Parser generado y validado",
            "runtime_name": "crewai",
            "completed": True,
        },
    )
    assert agent_run.status_code == 201
    agent_run_payload = agent_run.get_json()
    assert agent_run_payload["completed_at"] is not None
    agent_run_id = agent_run_payload["id"]

    task_execution = client.post(
        f"/api/blueprints/{blueprint_id}/task-executions",
        json={
            "delivery_task_id": delivery_task_id,
            "agent_run_id": agent_run_id,
            "status": "done",
            "attempt_number": 2,
            "summary": "Ticket completado tras un retry",
            "completed": True,
        },
    )
    assert task_execution.status_code == 201
    task_execution_payload = task_execution.get_json()
    assert task_execution_payload["completed_at"] is not None
    task_execution_id = task_execution_payload["id"]

    artifact = client.post(
        f"/api/blueprints/{blueprint_id}/artifacts",
        json={
            "agent_run_id": agent_run_id,
            "task_execution_id": task_execution_id,
            "name": "parser.py",
            "artifact_type": "code",
            "uri": "/workspace/parser.py",
        },
    )
    assert artifact.status_code == 201

    handoff = client.post(
        f"/api/blueprints/{blueprint_id}/handoffs",
        json={
            "task_execution_id": task_execution_id,
            "from_agent": "Jarvis-Dev",
            "to_agent": "Jarvis-QA",
            "status": "completed",
            "reason": "Enviar a validacion QA",
            "context": {"ticket_id": "TICKET-001"},
        },
    )
    assert handoff.status_code == 201

    invocation = client.post(
        f"/api/blueprints/{blueprint_id}/llm-invocations",
        json={
            "agent_run_id": agent_run_id,
            "provider": "ollama",
            "model": "qwen2.5-coder:latest",
            "purpose": "implementation",
            "status": "completed",
            "prompt_tokens": 120,
            "completion_tokens": 340,
            "latency_ms": 850,
            "cost_usd": 0.0,
        },
    )
    assert invocation.status_code == 201

    timeline_response = client.get(f"/api/blueprints/{blueprint_id}/timeline")
    assert timeline_response.status_code == 200
    timeline = timeline_response.get_json()["timeline"]
    event_types = {item["event_type"] for item in timeline}
    assert "blueprint_created" in event_types
    assert "sprint_cycle" in event_types
    assert "sprint_stage_event" in event_types
    assert "agent_run" in event_types
    assert "task_execution" in event_types
    assert "artifact" in event_types
    assert "handoff" in event_types
    assert "llm_invocation" in event_types

    report_response = client.get(f"/api/blueprints/{blueprint_id}/report")
    assert report_response.status_code == 200
    report = report_response.get_json()
    assert report["counts"]["sprint_cycles"] == 1
    assert report["counts"]["agent_runs"] == 1
    assert report["counts"]["task_executions"] == 1
    assert report["counts"]["artifacts"] == 1
    assert report["counts"]["handoffs"] == 1
    assert report["counts"]["llm_invocations"] == 1
    assert report["status_breakdown"]["sprint_cycles"]["active"] == 1
    assert report["delivery_metrics"]["retry_rate"] == 1.0
    assert report["llm"]["provider_breakdown"]["ollama"]["invocations"] == 1


def test_execution_tracking_rejects_invalid_stage_status(configured_app_with_specs):
    app, _, requirements_path, roadmap_path = configured_app_with_specs
    client = app.test_client()

    import_response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    blueprint_id = import_response.get_json()["id"]

    response = client.post(
        f"/api/blueprints/{blueprint_id}/stage-events",
        json={
            "stage_name": "planning",
            "status": "approved",
            "summary": "estado invalido",
        },
    )

    assert response.status_code == 400
    assert "Invalid status" in response.get_json()["error"]


def test_sprint_cycle_rejects_invalid_status(configured_app_with_specs):
    app, _, requirements_path, roadmap_path = configured_app_with_specs
    client = app.test_client()

    import_response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    blueprint_id = import_response.get_json()["id"]

    response = client.post(
        f"/api/blueprints/{blueprint_id}/sprint-cycles",
        json={
            "name": "Sprint 1",
            "status": "approved",
        },
    )

    assert response.status_code == 400
    assert "Invalid sprint status" in response.get_json()["error"]
