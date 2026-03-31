import importlib
import sys
from pathlib import Path

import pytest


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    if module_name == "app":
        for loaded_module in list(sys.modules):
            if (
                loaded_module.startswith("autonomous_delivery")
                or loaded_module.startswith("autonomous_scrum")
                or loaded_module.startswith("delivery_tracking")
                or loaded_module.startswith("crew_runtime")
            ):
                sys.modules.pop(loaded_module, None)
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


@pytest.fixture
def example_project_dossier_paths():
    project_root = Path(__file__).resolve().parents[1]
    dossier_root = project_root / "docs" / "example_project_2"
    return [
        dossier_root / "VEO3_CLAUDE_INTEGRATION_ROADMAP.md",
        dossier_root / "AGENTIC_WORKFLOW_CLASS_DIAGRAM.md",
    ]


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
    assert blueprint.certified_input is not None
    assert blueprint.certified_input.contract_name == "mission_control_certified_input"
    assert blueprint.certified_input.certification_status == "ready_for_planning"
    assert blueprint.certified_input.technology_guidance is not None
    assert blueprint.certified_input.technology_guidance.philosophy == "python_first"
    assert blueprint.certified_input.architecture_synthesis is not None
    assert blueprint.certified_input.confidence_assessment is not None
    assert blueprint.certified_input.question_budget is not None
    assert blueprint.certified_input.human_escalation is not None
    assert blueprint.certified_input.architecture_synthesis.nfr_candidates
    assert blueprint.certified_input.architecture_synthesis.technical_contracts
    assert blueprint.certified_input.architecture_synthesis.adr_bootstrap
    assert blueprint.certified_input.confidence_assessment.recommended_status == "ready_for_planning"
    assert blueprint.certified_input.question_budget.open_questions_count == 0
    assert blueprint.certified_input.human_escalation.required is False
    assert "Python" in blueprint.certified_input.technology_guidance.selection_policy
    assert any(
        document.doc_type == "requirements.generated.md"
        for document in blueprint.certified_input.documents
    )
    assert any(
        document.doc_type == "technical_contracts.initial.md"
        for document in blueprint.certified_input.documents
    )
    assert any(
        document.doc_type == "adr_bootstrap.md"
        for document in blueprint.certified_input.documents
    )


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
    assert payload["certified_input"]["contract_name"] == "mission_control_certified_input"
    assert payload["certified_input"]["certification_status"] == "ready_for_planning"
    assert payload["certified_input"]["documents"][0]["doc_type"] == "requirements.generated.md"
    assert payload["certified_input"]["technology_guidance"]["philosophy"] == "python_first"
    assert payload["certified_input"]["architecture_synthesis"]["nfr_candidates"]
    assert payload["certified_input"]["confidence_assessment"]["recommended_status"] == "ready_for_planning"
    assert payload["certified_input"]["human_escalation"]["required"] is False


def test_certified_input_highlights_platform_exceptions(tmp_path):
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"

    requirements_path.write_text(
        """# Workforce Platform
**Framework**: CrewAI

## Aplicaciones Cliente
La solucion debe incluir aplicaciones para Android, iOS, Windows, Linux y Mac.
- Debe registrar asistencia
- Debe sincronizar tareas
""",
        encoding="utf-8",
    )

    roadmap_path.write_text(
        """# Roadmap
**Proyecto**: Workforce Platform

## EP-0 · Setup
> Objetivo: dejar lista la base del producto.

### TICKET-001 · Preparar arquitectura inicial
```
Tipo: feature
Prioridad: P0
Est.: 4 h
Deps.: ninguna
```

**Descripción**
Definir arquitectura inicial.

**Criterios de aceptación**
- [ ] Define stack base
""",
        encoding="utf-8",
    )

    service_module = load_module("spec_intake.service")
    service = service_module.SpecIntakeService()
    blueprint = service.build_blueprint(
        requirements_path=requirements_path,
        roadmap_path=roadmap_path,
    )

    notes = blueprint.certified_input.technology_guidance.decision_notes
    assert any("Android" in note or "Kotlin" in note for note in notes)
    assert any("iOS" in note or "Swift" in note for note in notes)
    assert any("desktop multiplataforma" in note for note in notes)


def test_dependency_parser_expands_ranges():
    parser_module = load_module("spec_intake.parser")

    assert parser_module.parse_dependencies("TICKET-006 al TICKET-008") == [
        "TICKET-006",
        "TICKET-007",
        "TICKET-008",
    ]
    assert parser_module.parse_dependencies("TICKET-030 (smoke test OK)") == ["TICKET-030"]
    assert parser_module.parse_dependencies("todos los agentes") == []


def test_input_artifact_classifier_detects_shapes(sample_spec_files):
    requirements_path, roadmap_path = sample_spec_files
    flexible_inputs_module = load_module("spec_intake.flexible_inputs")

    formal_pair = flexible_inputs_module.classify_input_artifacts(
        [requirements_path, roadmap_path]
    )
    assert formal_pair.shape_kind == "formal_pair"

    dossier = flexible_inputs_module.classify_input_artifacts(
        [
            "docs/example_project_2/VEO3_CLAUDE_INTEGRATION_ROADMAP.md",
            "docs/example_project_2/AGENTIC_WORKFLOW_CLASS_DIAGRAM.md",
        ]
    )
    assert dossier.shape_kind == "roadmap_dossier"

    use_case_only = flexible_inputs_module.classify_input_artifacts(
        [
            {
                "label": "chat-brief.md",
                "content": (
                    "Quiero un sistema de gestion de firmas y asistencia para RRHH "
                    "con contratos en Ethereum y calculo de salarios por hora."
                ),
            }
        ]
    )
    assert use_case_only.shape_kind == "use_case_only"


def test_spec_intake_service_builds_blueprint_from_input_artifacts(sample_spec_files):
    requirements_path, roadmap_path = sample_spec_files
    service_module = load_module("spec_intake.service")
    service = service_module.SpecIntakeService()

    blueprint = service.build_blueprint_from_input_artifacts(
        input_artifacts=[
            {"path": requirements_path, "role": "requirements"},
            {"path": roadmap_path, "role": "roadmap"},
        ]
    )

    assert blueprint.project_name == "Plataforma de Automatizacion"
    assert blueprint.certified_input.source_input_kind == "formal_pair"
    assert blueprint.certified_input.certification_status == "ready_for_planning"


def test_spec_intake_service_normalizes_example_project_dossier(example_project_dossier_paths):
    service_module = load_module("spec_intake.service")
    service = service_module.SpecIntakeService()

    blueprint = service.build_blueprint_from_input_artifacts(
        input_artifacts=example_project_dossier_paths
    )

    assert blueprint.project_name == "legatus-video-factory"
    assert len(blueprint.requirements) >= 8
    assert len(blueprint.roadmap_epics) >= 5
    assert sum(len(epic.tickets) for epic in blueprint.roadmap_epics) >= 10
    assert blueprint.certified_input is not None
    assert blueprint.certified_input.source_input_kind == "roadmap_dossier"
    assert blueprint.certified_input.certification_status == "needs_operator_review"
    assert blueprint.certified_input.human_escalation.required is True
    assert any(epic.name.startswith("Fase 0") for epic in blueprint.roadmap_epics)


def test_architecture_synthesizer_closes_gaps_for_open_use_case():
    service_module = load_module("spec_intake.service")
    service = service_module.SpecIntakeService()

    blueprint = service.build_blueprint_from_input_artifacts(
        input_artifacts=[
            {
                "label": "chat-brief.md",
                "content": (
                    "Quiero un sistema de gestion de firmas de recursos humanos donde puedan contratar, "
                    "firmar contrato usando ethereum contracts, que los empleados registren su asistencia "
                    "y hora de inicio de labores en una aplicacion windows/linux/mac os, registren tareas "
                    "y se calculen salarios por hora por individuo."
                ),
            }
        ]
    )

    assert blueprint.certified_input is not None
    assert blueprint.certified_input.source_input_kind == "use_case_only"
    assert blueprint.certified_input.certification_status == "needs_operator_review"
    architecture = blueprint.certified_input.architecture_synthesis
    assert architecture is not None
    assert any(contract.name == "Gateway de Firma y Settlement en Ethereum" for contract in architecture.technical_contracts)
    assert any(contract.name == "Cliente de Asistencia y Sincronizacion" for contract in architecture.technical_contracts)
    assert any(candidate.category == "auditability" for candidate in architecture.nfr_candidates)
    assert any(candidate.category == "determinism" for candidate in architecture.nfr_candidates)
    assert any("wallets" in question.lower() or "gas" in question.lower() for question in architecture.open_questions)
    assert blueprint.certified_input.question_budget is not None
    assert blueprint.certified_input.question_budget.critical_questions_count >= 1
    assert blueprint.certified_input.human_escalation is not None
    assert blueprint.certified_input.human_escalation.required is True
    assert blueprint.certified_input.human_escalation.recommended_action == "operator_review"
    assert any(
        "backend central" in document.content.lower()
        for document in blueprint.certified_input.documents
        if document.doc_type == "nfrs.candidates.md"
    )


def test_vague_use_case_is_marked_as_insufficient_input():
    service_module = load_module("spec_intake.service")
    service = service_module.SpecIntakeService()

    blueprint = service.build_blueprint_from_input_artifacts(
        input_artifacts=[
            {
                "label": "brief.md",
                "content": "Necesito una app.",
            }
        ]
    )

    certified_input = blueprint.certified_input
    assert certified_input is not None
    assert certified_input.source_input_kind == "use_case_only"
    assert certified_input.confidence_assessment is not None
    assert certified_input.confidence_assessment.score < certified_input.confidence_assessment.review_threshold
    assert certified_input.confidence_assessment.recommended_status == "insufficient_input"
    assert certified_input.human_escalation is not None
    assert certified_input.human_escalation.recommended_action == "collect_more_input"
    assert certified_input.certification_status == "insufficient_input"
