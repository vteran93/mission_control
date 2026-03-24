import importlib
import sys

import pytest


def load_app_stack():
    for module_name in list(sys.modules):
        if (
            module_name == "app"
            or module_name == "database"
            or module_name.startswith("spec_intake")
            or module_name.startswith("delivery_tracking")
            or module_name.startswith("autonomous_scrum")
        ):
            sys.modules.pop(module_name, None)
    database_module = importlib.import_module("database")
    app_module = importlib.import_module("app")
    return app_module, database_module


@pytest.fixture
def configured_phase4_app(tmp_path, monkeypatch):
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"
    database_path = tmp_path / "instance" / "phase4.db"

    requirements_path.write_text(
        """# Mission Control Planner
## Objetivo
- Debe planificar sprints automaticamente
- Debe versionar el backlog
- Debe registrar ceremonias SCRUM

## Riesgos
- Debe detectar tickets bloqueados
- Debe proponer replanificacion cuando baje la confianza
""",
        encoding="utf-8",
    )

    roadmap_path.write_text(
        """# Roadmap
**Proyecto**: Mission Control Planner

## EP-4 · Autonomous Scrum Planner
> Objetivo: generar sprints ejecutables desde el blueprint.

### TICKET-401 · Normalizar backlog inicial
```
Tipo: feature
Prioridad: P0
Est.: 4 h
Deps.: ninguna
```

**Descripción**
Construir backlog inicial derivado del blueprint.

**Criterios de aceptación**
- [ ] Genera tareas normalizadas
- [ ] Preserva dependencias

### TICKET-402 · Planificar capacidad por sprint
```
Tipo: feature
Prioridad: P0
Est.: 8 h
Deps.: TICKET-401
```

**Descripción**
Distribuir tickets por sprint segun capacidad efectiva.

**Criterios de aceptación**
- [ ] Agrupa tickets por sprint
- [ ] Respeta dependencias

### TICKET-403 · Replanificar por riesgo
```
Tipo: feature
Prioridad: P1
Est.: 8 h
Deps.: TICKET-402
```

**Descripción**
Recalcular el plan si aparecen bloqueos o cambios de alcance.

**Criterios de aceptación**
- [ ] Genera un plan nuevo
- [ ] Mantiene trazabilidad de versiones

### TICKET-404 · QA del plan autonomo
```
Tipo: qa
Prioridad: P1
Est.: 4 h
Deps.: TICKET-403
```

**Descripción**
Validar readiness, DoR y DoD del plan generado.

**Criterios de aceptación**
- [ ] Cada ticket tiene DoR
- [ ] Cada ticket tiene DoD
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


def import_phase4_blueprint(client, requirements_path, roadmap_path):
    response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    assert response.status_code == 201
    return response.get_json()


def test_autonomous_scrum_planner_generates_plan_and_ceremonies(configured_phase4_app):
    app, _, requirements_path, roadmap_path = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        json={
            "sprint_capacity": 5,
            "sprint_length_days": 7,
            "start_date": "2026-03-24T09:00:00",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["version"] == 1
    assert payload["summary"]["sprints_planned"] == 2
    assert payload["escalation_trigger"] == "none"
    assert len(payload["sprint_cycles"]) == 2
    assert len(payload["items"]) == 4

    items_by_ticket = {item["ticket_id"]: item for item in payload["items"]}
    assert items_by_ticket["TICKET-401"]["sprint_order"] == 1
    assert items_by_ticket["TICKET-402"]["sprint_order"] == 1
    assert items_by_ticket["TICKET-403"]["sprint_order"] == 2
    assert items_by_ticket["TICKET-404"]["assignee_role"] == "jarvis-qa"
    assert items_by_ticket["TICKET-401"]["definition_of_ready"]
    assert items_by_ticket["TICKET-404"]["definition_of_done"]

    ceremonies = {item["stage_name"] for item in payload["ceremonies"]}
    assert ceremonies == {"planning", "daily_summary", "review", "retrospective"}
    assert payload["planning_feedback"][0]["feedback_text"].startswith("[ScrumPlan v1]")

    detail_response = client.get(f"/api/blueprints/{blueprint_id}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()
    assert detail["summary"]["scrum_plans_count"] == 1
    assert detail["summary"]["scrum_plan_items_count"] == 4


def test_autonomous_scrum_planner_replans_and_supersedes_previous_version(configured_phase4_app):
    app, database_module, requirements_path, roadmap_path = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    first_plan_response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        json={"sprint_capacity": 5},
    )
    assert first_plan_response.status_code == 201

    replan_response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan/replan",
        json={
            "sprint_capacity": 5,
            "blocked_ticket_ids": ["TICKET-402"],
            "changed_ticket_ids": ["TICKET-403"],
            "reason": "Cambio de alcance en la integracion del planner",
        },
    )

    assert replan_response.status_code == 201
    payload = replan_response.get_json()
    assert payload["version"] == 2
    assert payload["planning_mode"] == "replan"
    assert payload["escalation_trigger"] == "blocked_dependency"

    items_by_ticket = {item["ticket_id"]: item for item in payload["items"]}
    assert items_by_ticket["TICKET-402"]["plan_status"] == "blocked"
    assert items_by_ticket["TICKET-403"]["plan_status"] == "blocked"

    latest_response = client.get(f"/api/blueprints/{blueprint_id}/scrum-plan")
    assert latest_response.status_code == 200
    assert latest_response.get_json()["version"] == 2

    plans_response = client.get(f"/api/blueprints/{blueprint_id}/scrum-plans")
    assert plans_response.status_code == 200
    plans = plans_response.get_json()
    assert [item["version"] for item in plans] == [2, 1]
    assert plans[0]["status"] == "active"
    assert plans[1]["status"] == "superseded"

    with app.app_context():
        first_plan = (
            database_module.ScrumPlanRecord.query.filter_by(project_blueprint_id=blueprint_id, version=1).first()
        )
        second_plan = (
            database_module.ScrumPlanRecord.query.filter_by(project_blueprint_id=blueprint_id, version=2).first()
        )
        assert first_plan is not None and first_plan.status == "superseded"
        assert second_plan is not None and second_plan.status == "active"


def test_planner_updates_timeline_and_report_counts(configured_phase4_app):
    app, _, requirements_path, roadmap_path = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        json={"sprint_capacity": 5},
    )
    assert response.status_code == 201

    timeline_response = client.get(f"/api/blueprints/{blueprint_id}/timeline")
    assert timeline_response.status_code == 200
    timeline = timeline_response.get_json()["timeline"]
    event_types = {item["event_type"] for item in timeline}
    assert "scrum_plan" in event_types
    assert "scrum_plan_item" in event_types

    report_response = client.get(f"/api/blueprints/{blueprint_id}/report")
    assert report_response.status_code == 200
    report = report_response.get_json()
    assert report["counts"]["scrum_plans"] == 1
    assert report["counts"]["scrum_plan_items"] == 4
    assert report["delivery_metrics"]["planned_task_count"] == 4
    assert report["delivery_metrics"]["blocked_planning_count"] == 0
