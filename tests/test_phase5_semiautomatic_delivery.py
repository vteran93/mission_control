import importlib
import subprocess
import sys
import types

import pytest


def load_app_stack():
    for module_name in list(sys.modules):
        if (
            module_name in {"app", "config", "database"}
            or module_name.startswith("spec_intake")
            or module_name.startswith("delivery_tracking")
            or module_name.startswith("autonomous_scrum")
            or module_name.startswith("autonomous_delivery")
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

        def __init__(self, **kwargs):
            FakeCrew.last_kwargs = kwargs
            self.kwargs = kwargs

        def kickoff(self):
            if FakeCrew.kickoff_plan:
                next_item = FakeCrew.kickoff_plan.pop(0)
                if isinstance(next_item, Exception):
                    raise next_item
                return next_item
            return types.SimpleNamespace(
                raw='{"approval_status":"approved","summary":"ok","risks":[],"actions":["ejecutar"]}'
            )

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
def configured_phase5_app(tmp_path, monkeypatch):
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"
    workspace_root = tmp_path / "target_workspace"
    database_path = tmp_path / "instance" / "phase5.db"

    requirements_path.write_text(
        """# Mission Control Delivery
## Objetivo
- Debe ejecutar un modo semiautomatico para materializar artefactos simples
- Debe escribir archivos reales en el workspace del proyecto
- Debe dejar evidencia de ejecucion y artefactos en Postgres
""",
        encoding="utf-8",
    )

    roadmap_path.write_text(
        """# Roadmap
**Proyecto**: Mission Control Delivery

## EP-5 · Autonomous Delivery Loop
> Objetivo: ejecutar artefactos simples en modo semiautomatico.

### TICKET-501 · Escribir examples/holamundo.py
```
Tipo: feature
Prioridad: P0
Est.: 1 h
Deps.: ninguna
```

**Descripción**
Crear un archivo Python en examples/holamundo.py que imprima Hola Mundo.

**Criterios de aceptación**
- [ ] Existe examples/holamundo.py
- [ ] El script imprime Hola Mundo al ejecutarse

### TICKET-502 · Escribir pagina React Hola Mundo en frontend
```
Tipo: feature
Prioridad: P1
Est.: 2 h
Deps.: ninguna
```

**Descripción**
Crear una pagina web con React JS Hola Mundo en una carpeta frontend.

**Criterios de aceptación**
- [ ] Existe frontend/index.html
- [ ] La pagina monta un root de React
- [ ] La pagina muestra Hola Mundo

### TICKET-503 · Escribir modulo Terraform S3 en infra
```
Tipo: feature
Prioridad: P1
Est.: 2 h
Deps.: ninguna
```

**Descripción**
Crear un modulo de Terraform con un recurso S3 basico en una carpeta infra.

**Criterios de aceptación**
- [ ] Existe infra/main.tf
- [ ] El modulo declara aws_s3_bucket.basic
- [ ] El bucket usa una variable bucket_name
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

    return app, database_module, requirements_path, roadmap_path, workspace_root, fake_crew_class


def import_blueprint(client, requirements_path, roadmap_path):
    response = client.post(
        "/api/blueprints/import",
        json={
            "requirements_path": str(requirements_path),
            "roadmap_path": str(roadmap_path),
        },
    )
    assert response.status_code == 201
    return response.get_json()


def test_semiautomatic_delivery_executes_ready_plan_and_writes_workspace_artifacts(
    configured_phase5_app,
):
    app, database_module, requirements_path, roadmap_path, workspace_root, fake_crew_class = configured_phase5_app
    client = app.test_client()
    blueprint = import_blueprint(client, requirements_path, roadmap_path)
    blueprint_id = blueprint["id"]

    fake_crew_class.kickoff_plan = [
        types.SimpleNamespace(
            raw='{"approval_status":"approved","summary":"Plan listo para ejecucion semiautomatica","risks":[],"actions":["ejecutar"]}'
        )
    ]
    plan_response = client.post(
        f"/api/blueprints/{blueprint_id}/scrum-plan",
        json={"sprint_capacity": 12},
    )
    assert plan_response.status_code == 201
    plan = plan_response.get_json()
    assert plan["approval_status"] == "approved"

    execute_response = client.post(
        f"/api/blueprints/{blueprint_id}/delivery/execute",
        json={
            "workspace_root": str(workspace_root),
            "execution_mode": "semi_automatic",
        },
    )
    assert execute_response.status_code == 201
    payload = execute_response.get_json()
    assert payload["summary"]["ok"] is True
    assert payload["summary"]["executed_item_count"] == 3
    assert payload["summary"]["written_file_count"] == 5

    files_by_ticket = {item["ticket_id"]: item["files"] for item in payload["executions"]}
    assert files_by_ticket["TICKET-501"] == ["examples/holamundo.py"]
    assert files_by_ticket["TICKET-502"] == ["frontend/index.html"]
    assert files_by_ticket["TICKET-503"] == [
        "infra/main.tf",
        "infra/variables.tf",
        "infra/outputs.tf",
    ]

    python_script = workspace_root / "examples" / "holamundo.py"
    react_page = workspace_root / "frontend" / "index.html"
    terraform_main = workspace_root / "infra" / "main.tf"

    assert python_script.exists()
    assert react_page.exists()
    assert terraform_main.exists()

    python_result = subprocess.run(
        ["python3", str(python_script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert python_result.returncode == 0
    assert python_result.stdout.strip() == "Hola Mundo"

    react_content = react_page.read_text(encoding="utf-8")
    assert "createRoot" in react_content
    assert "Hola Mundo" in react_content

    terraform_content = terraform_main.read_text(encoding="utf-8")
    assert 'resource "aws_s3_bucket" "basic"' in terraform_content
    assert "bucket = var.bucket_name" in terraform_content

    report_response = client.get(f"/api/blueprints/{blueprint_id}/report")
    assert report_response.status_code == 200
    report = report_response.get_json()
    assert report["counts"]["agent_runs"] == 4
    assert report["counts"]["task_executions"] == 3
    assert report["counts"]["artifacts"] == 5
    assert report["status_breakdown"]["task_executions"]["done"] == 3

    timeline_response = client.get(f"/api/blueprints/{blueprint_id}/timeline")
    assert timeline_response.status_code == 200
    timeline = timeline_response.get_json()["timeline"]
    execution_events = [
        item
        for item in timeline
        if item["event_type"] == "sprint_stage_event"
        and item["payload"]["source"] == "semi_automatic_delivery"
    ]
    assert {item["payload"]["stage_name"] for item in execution_events} == {"execution", "qa_gate"}

    with app.app_context():
        assert database_module.AgentRunRecord.query.count() == 4
        assert database_module.TaskExecutionRecord.query.count() == 3
        assert database_module.ArtifactRecord.query.count() == 5
