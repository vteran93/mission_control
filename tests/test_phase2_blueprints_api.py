import importlib
import sys

import pytest


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def load_app_stack():
    for module_name in list(sys.modules):
        if module_name == "app" or module_name == "database" or module_name.startswith("spec_intake"):
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
