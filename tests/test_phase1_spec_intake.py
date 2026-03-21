import importlib
import sys
from pathlib import Path

import pytest


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


@pytest.fixture
def sample_spec_files(tmp_path):
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"

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

## Modelo de Datos
Persistir blueprints, tickets y feedback.
- Debe registrar backlog
- Debe registrar retrospective
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

### TICKET-002 · Validar dependencias
```
Tipo: feature
Prioridad: P1
Est.: 2 h
Deps.: TICKET-001
```

**Descripción**
Validar dependencias del roadmap.

**Criterios de aceptación**
- [ ] Detecta dependencias desconocidas
""",
        encoding="utf-8",
    )

    return requirements_path, roadmap_path


def test_spec_intake_service_builds_blueprint(sample_spec_files):
    requirements_path, roadmap_path = sample_spec_files
    service_module = load_module("spec_intake.service")
    service = service_module.SpecIntakeService()

    blueprint = service.build_blueprint(
        requirements_path=requirements_path,
        roadmap_path=roadmap_path,
    )

    assert blueprint.project_name == "Plataforma de Automatizacion"
    assert len(blueprint.requirements) >= 3
    assert len(blueprint.roadmap_epics) == 1
    assert blueprint.roadmap_epics[0].epic_id == "EP-0"
    assert len(blueprint.roadmap_epics[0].tickets) == 2
    assert "Arquitectura" in blueprint.capabilities
    assert "Parsea Markdown" in blueprint.acceptance_items[0]
    assert blueprint.roadmap_epics[0].tickets[1].dependencies == ["TICKET-001"]


def test_spec_intake_preview_endpoint_returns_blueprint(sample_spec_files, tmp_path, monkeypatch):
    requirements_path, roadmap_path = sample_spec_files
    database_path = tmp_path / "instance" / "test.db"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("MISSION_CONTROL_INSTANCE_PATH", str(tmp_path / "instance"))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("MISSION_CONTROL_QUEUE_DIR", str(tmp_path / "runtime" / "queue"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_LOCK_DIR", str(tmp_path / "runtime" / "locks"))
    monkeypatch.setenv("MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR", str(tmp_path / "scripts"))

    app_module = load_module("app")
    app = app_module.create_app()

    with app.app_context():
        app_module.db.create_all()

    client = app.test_client()
    response = client.post(
        "/api/spec-intake/preview",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["project_name"] == "Plataforma de Automatizacion"
    assert payload["summary"]["tickets_count"] == 2
    assert payload["summary"]["requirements_count"] >= 3


def test_dependency_parser_expands_ranges():
    parser_module = load_module("spec_intake.parser")

    assert parser_module.parse_dependencies("TICKET-006 al TICKET-008") == [
        "TICKET-006",
        "TICKET-007",
        "TICKET-008",
    ]
    assert parser_module.parse_dependencies("TICKET-030 (smoke test OK)") == ["TICKET-030"]
    assert parser_module.parse_dependencies("todos los agentes") == []
