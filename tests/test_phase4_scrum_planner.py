import importlib
import sys
import types

import pytest


def load_app_stack():
    for module_name in list(sys.modules):
        if (
            module_name in {"app", "config", "database"}
            or module_name.startswith("autonomous_delivery")
            or module_name.startswith("spec_intake")
            or module_name.startswith("delivery_tracking")
            or module_name.startswith("autonomous_scrum")
            or module_name.startswith("crew_runtime")
        ):
            sys.modules.pop(module_name, None)
    database_module = importlib.import_module("database")
    app_module = importlib.import_module("app")
    return app_module, database_module


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
            return types.SimpleNamespace(raw='{"approval_status":"approved","summary":"ok","risks":[],"actions":[]}')

    class FakeProcess:
        hierarchical = "hierarchical"

    fake_crewai.Agent = FakeAgent
    fake_crewai.Crew = FakeCrew
    fake_crewai.Task = FakeTask
    fake_crewai.Process = FakeProcess
    fake_crewai.LLM = FakeLLM
    monkeypatch.setitem(sys.modules, "crewai", fake_crewai)
    return FakeCrew


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

    fake_crew_class = install_fake_crewai(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MISSION_CONTROL_INSTANCE_PATH", str(tmp_path / "instance"))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("MISSION_CONTROL_QUEUE_DIR", str(tmp_path / "runtime" / "queue"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", str(tmp_path / "runtime" / "locks"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", str(tmp_path / "scripts"))
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_EXECUTOR", "crewai")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_AUTOSTART", "false")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_ENABLE_FALLBACK", "true")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_ESCALATE_AFTER_RETRIES", "1")
    monkeypatch.setenv("MISSION_CONTROL_LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("MISSION_CONTROL_LLM_MAX_TOKENS", "2048")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:latest")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("BEDROCK_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_PLANNER_MODEL", "anthropic.claude-3-7-sonnet")
    monkeypatch.setenv("BEDROCK_REVIEWER_MODEL", "anthropic.claude-3-5-sonnet")

    app_module, database_module = load_app_stack()
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

    fake_crew_class.kickoff_history = []
    fake_crew_class.kickoff_plan = []
    return app, database_module, requirements_path, roadmap_path, fake_crew_class


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


def approved_output(summary: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        raw=(
            '{"approval_status":"approved","summary":"%s","risks":[],"actions":["ejecutar"]}'
            % summary
        )
    )


def review_required_output(summary: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        raw=(
            '{"approval_status":"review_required","summary":"%s","risks":["alto riesgo"],"actions":["revisar"]}'
            % summary
        )
    )


def test_scrum_planner_runs_mandatory_planning_crew_before_persisting(configured_phase4_app):
    app, database_module, requirements_path, roadmap_path, fake_crew_class = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]
    fake_crew_class.kickoff_plan = [approved_output("Plan listo para ejecutar")]

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
    assert payload["status"] == "active"
    assert payload["approval_status"] == "approved"
    assert payload["summary"]["execution_ready"] is True
    assert payload["summary"]["planning_crew"]["approval_status"] == "approved"
    assert payload["summary"]["planning_crew"]["metadata"]["provider"] == "bedrock"
    assert payload["summary"]["sprints_planned"] == 2
    assert payload["escalation_trigger"] == "none"
    assert len(payload["sprint_cycles"]) == 2
    assert len(payload["items"]) == 4

    stage_names = {item["stage_name"] for item in payload["ceremonies"]}
    assert stage_names == {"planning", "daily_summary", "review", "retrospective"}
    feedback_labels = {item["source"] for item in payload["planning_feedback"]}
    assert "planning_crew" in feedback_labels
    assert fake_crew_class.kickoff_history[-1]["name"] == "scrum_planning"

    with app.app_context():
        assert database_module.ScrumPlanRecord.query.count() == 1


def test_scrum_planner_blocks_persistence_when_planning_crew_fails(configured_phase4_app):
    app, database_module, requirements_path, roadmap_path, fake_crew_class = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]
    fake_crew_class.kickoff_plan = [RuntimeError("crewai unavailable")]

    response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        json={"sprint_capacity": 5},
    )

    assert response.status_code == 409
    assert "CrewAI dispatch fallo" in response.get_json()["error"]

    with app.app_context():
        assert database_module.ScrumPlanRecord.query.count() == 0
        assert database_module.ScrumPlanItemRecord.query.count() == 0


def test_scrum_planner_replans_and_supersedes_previous_version_when_approved(configured_phase4_app):
    app, database_module, requirements_path, roadmap_path, fake_crew_class = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]
    fake_crew_class.kickoff_plan = [
        approved_output("Plan inicial aprobado"),
        approved_output("Replan aprobado"),
    ]

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
    assert payload["status"] == "active"
    assert payload["approval_status"] == "approved"
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
        assert second_plan.approval_status == "approved"


def test_bedrock_review_can_leave_latest_plan_pending_review_and_sprint_view_exposes_readiness(
    configured_phase4_app,
    monkeypatch,
):
    app, _, requirements_path, roadmap_path, fake_crew_class = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    fake_crew_class.kickoff_plan = [approved_output("Plan base aprobado")]
    first_plan_response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        json={"sprint_capacity": 5},
    )
    assert first_plan_response.status_code == 201

    planner_service = app.extensions["autonomous_scrum_service"]
    monkeypatch.setattr(
        planner_service,
        "_compute_confidence",
        lambda task_drafts, *, blueprint_issue_count: 0.4,
    )
    fake_crew_class.kickoff_plan = [
        review_required_output("Planning crew detecta bajo nivel de confianza"),
        review_required_output("Bedrock senior requiere revision adicional"),
    ]

    second_plan_response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan/replan",
        json={"sprint_capacity": 5, "reason": "Reducir confianza para disparar Bedrock"},
    )

    assert second_plan_response.status_code == 201
    payload = second_plan_response.get_json()
    assert payload["version"] == 2
    assert payload["status"] == "draft"
    assert payload["approval_status"] == "review_required"
    assert payload["escalation_trigger"] == "bedrock_review"
    assert payload["summary"]["execution_ready"] is False
    assert payload["summary"]["senior_review"]["approval_status"] == "review_required"
    assert payload["summary"]["senior_review"]["metadata"]["provider"] == "bedrock"

    default_plan_response = client.get(f"/api/blueprints/{blueprint_id}/scrum-plan")
    assert default_plan_response.status_code == 200
    assert default_plan_response.get_json()["version"] == 1
    assert default_plan_response.get_json()["approval_status"] == "approved"

    latest_plan_response = client.get(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        query_string={"status": "latest"},
    )
    assert latest_plan_response.status_code == 200
    assert latest_plan_response.get_json()["version"] == 2

    sprint_view_response = client.get(
        f"/api/blueprints/{blueprint_id}/scrum-plan/sprint-view",
        query_string={"status": "latest"},
    )
    assert sprint_view_response.status_code == 200
    sprint_view = sprint_view_response.get_json()
    assert sprint_view["plan"]["version"] == 2
    assert sprint_view["plan"]["approval_status"] == "review_required"
    assert sprint_view["summary"]["overall_readiness"] == "review_required"
    assert sprint_view["summary"]["total_consumed_capacity"] > 0
    assert sprint_view["sprints"][0]["execution_ready"] is False


def test_planner_updates_timeline_report_and_supports_manual_approval(configured_phase4_app, monkeypatch):
    app, database_module, requirements_path, roadmap_path, fake_crew_class = configured_phase4_app
    client = app.test_client()
    blueprint = import_phase4_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    planner_service = app.extensions["autonomous_scrum_service"]
    monkeypatch.setattr(
        planner_service,
        "_compute_confidence",
        lambda task_drafts, *, blueprint_issue_count: 0.4,
    )
    fake_crew_class.kickoff_plan = [
        review_required_output("Planning crew requiere revision"),
        review_required_output("Bedrock senior no aprueba aun"),
    ]

    response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        json={"sprint_capacity": 5},
    )
    assert response.status_code == 201
    draft_plan = response.get_json()
    assert draft_plan["status"] == "draft"
    assert draft_plan["approval_status"] == "review_required"

    approve_response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan/{draft_plan['id']}/approve",
        json={"source": "manual_override", "feedback_text": "Aprobado para Fase 5"},
    )
    assert approve_response.status_code == 200
    approved_plan = approve_response.get_json()
    assert approved_plan["status"] == "active"
    assert approved_plan["approval_status"] == "approved"
    assert approved_plan["summary"]["execution_ready"] is True

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

    sprint_view_response = client.get(f"/api/blueprints/{blueprint_id}/scrum-plan/sprint-view")
    assert sprint_view_response.status_code == 200
    sprint_view = sprint_view_response.get_json()
    assert sprint_view["plan"]["execution_ready"] is True
    assert sprint_view["summary"]["overall_readiness"] in {"ready", "needs_clarification"}

    with app.app_context():
        plan = database_module.ScrumPlanRecord.query.one()
        assert plan.status == "active"
        assert plan.approval_status == "approved"
