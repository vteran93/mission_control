from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from autonomous_scrum import AutonomousScrumPlannerService
from config import Settings
from database import ProjectBlueprintRecord, db
from delivery_tracking import DeliveryTrackingService
from spec_intake import BlueprintPersistenceService

from .crew_seeds import CrewSeed


MAX_TOOL_OUTPUT_CHARS = 6000


@dataclass(frozen=True)
class RuntimeToolSpec:
    name: str
    category: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
        }


TOOL_SPECS: tuple[RuntimeToolSpec, ...] = (
    RuntimeToolSpec(
        name="mission_control_blueprint_context",
        category="mission_control",
        description="Devuelve contexto resumido de un blueprint, requirements, capabilities y backlog.",
    ),
    RuntimeToolSpec(
        name="mission_control_delivery_task_context",
        category="mission_control",
        description="Devuelve el contexto de un ticket derivado del roadmap dentro de un blueprint.",
    ),
    RuntimeToolSpec(
        name="mission_control_execution_report",
        category="mission_control",
        description="Devuelve el reporte agregado de ejecucion, retries, throughput y LLM usage.",
    ),
    RuntimeToolSpec(
        name="mission_control_scrum_plan_context",
        category="mission_control",
        description="Devuelve el Scrum plan activo, sprints, readiness, DoR/DoD y riesgo por ticket.",
    ),
    RuntimeToolSpec(
        name="mission_control_feedback_digest",
        category="mission_control",
        description="Resume feedback de etapas SCRUM y retrospective de un blueprint.",
    ),
    RuntimeToolSpec(
        name="mission_control_artifact_digest",
        category="mission_control",
        description="Lista artifacts e handoffs registrados para un blueprint.",
    ),
    RuntimeToolSpec(
        name="workspace_stack_context",
        category="workspace_context",
        description="Detecta stacks y package managers del workspace, incluyendo npm, NuGet/dotnet, Python, Cargo y Go.",
    ),
    RuntimeToolSpec(
        name="workspace_package_manager_context",
        category="workspace_context",
        description="Devuelve comandos y contexto operativo para npm, pnpm, yarn, NuGet/dotnet, pip, cargo o go.",
    ),
    RuntimeToolSpec(
        name="workspace_read_file",
        category="workspace_context",
        description="Lee un archivo del workspace con truncamiento seguro para analisis.",
    ),
    RuntimeToolSpec(
        name="workspace_write_file",
        category="workspace",
        description="Crea o actualiza archivos dentro del workspace para implementar codigo o configuracion.",
    ),
    RuntimeToolSpec(
        name="workspace_run_unix_command",
        category="workspace",
        description="Ejecuta comandos Unix controlados dentro del workspace y devuelve stdout, stderr y exit code.",
    ),
    RuntimeToolSpec(
        name="workspace_run_mypy",
        category="workspace",
        description="Ejecuta mypy sobre rutas del workspace para validar type checking de Python.",
    ),
    RuntimeToolSpec(
        name="workspace_run_tests",
        category="workspace",
        description="Ejecuta un comando de pruebas del workspace y devuelve el resultado estructurado.",
    ),
)


class RuntimeToolCatalog:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.workspace_root = settings.base_dir.resolve()
        self.persistence_service = BlueprintPersistenceService()
        self.delivery_tracking_service = DeliveryTrackingService()
        self.scrum_planner_service = AutonomousScrumPlannerService()

    def describe(self) -> list[dict[str, str]]:
        return [tool.to_dict() for tool in TOOL_SPECS]

    def describe_for_seed(self, seed: CrewSeed) -> list[dict[str, str]]:
        return [
            tool.to_dict()
            for tool in TOOL_SPECS
            if tool.category in seed.tool_groups
        ]

    def build_tools_for_seed(self, seed: CrewSeed) -> list[object]:
        selected_specs = [
            spec
            for spec in TOOL_SPECS
            if spec.category in seed.tool_groups
        ]

        try:
            from crewai.tools import tool
        except Exception:
            return selected_specs

        catalog = self

        @tool("mission_control_blueprint_context")
        def mission_control_blueprint_context(blueprint_id: int) -> str:
            """Devuelve el contexto resumido de un blueprint para planear o ejecutar trabajo."""
            return catalog._dump_payload(catalog.get_blueprint_context(blueprint_id))

        @tool("mission_control_delivery_task_context")
        def mission_control_delivery_task_context(blueprint_id: int, delivery_task_id: int) -> str:
            """Devuelve el contexto resumido de un delivery task dentro de un blueprint."""
            return catalog._dump_payload(
                catalog.get_delivery_task_context(
                    blueprint_id=blueprint_id,
                    delivery_task_id=delivery_task_id,
                )
            )

        @tool("mission_control_execution_report")
        def mission_control_execution_report(blueprint_id: int) -> str:
            """Devuelve el reporte agregado de ejecucion de un blueprint."""
            return catalog._dump_payload(catalog.delivery_tracking_service.build_report(blueprint_id))

        @tool("mission_control_scrum_plan_context")
        def mission_control_scrum_plan_context(blueprint_id: int, plan_id: int = 0) -> str:
            """Devuelve el Scrum plan activo o uno especifico por plan_id."""
            resolved_plan_id = plan_id or None
            return catalog._dump_payload(
                catalog.get_scrum_plan_context(blueprint_id=blueprint_id, plan_id=resolved_plan_id)
            )

        @tool("mission_control_feedback_digest")
        def mission_control_feedback_digest(blueprint_id: int) -> str:
            """Devuelve feedback SCRUM y retrospective de un blueprint."""
            return catalog._dump_payload(catalog.get_feedback_digest(blueprint_id))

        @tool("mission_control_artifact_digest")
        def mission_control_artifact_digest(blueprint_id: int) -> str:
            """Devuelve artifacts e handoffs registrados para un blueprint."""
            return catalog._dump_payload(catalog.get_artifact_digest(blueprint_id))

        @tool("workspace_stack_context")
        def workspace_stack_context(cwd: str = ".") -> str:
            """Detecta stacks, package managers y comandos recomendados del workspace."""
            return catalog._dump_payload(catalog.detect_workspace_stack(cwd=cwd))

        @tool("workspace_package_manager_context")
        def workspace_package_manager_context(ecosystem: str, cwd: str = ".") -> str:
            """Devuelve contexto operativo para npm, pnpm, yarn, NuGet/dotnet, pip, cargo o go."""
            return catalog._dump_payload(
                catalog.get_package_manager_context(ecosystem=ecosystem, cwd=cwd)
            )

        @tool("workspace_read_file")
        def workspace_read_file(path: str, max_chars: int = 4000) -> str:
            """Lee un archivo del workspace de forma segura para inspeccion y analisis."""
            return catalog.read_workspace_file(path=path, max_chars=max_chars)

        @tool("workspace_write_file")
        def workspace_write_file(path: str, content: str, overwrite: bool = True) -> str:
            """Crea o actualiza un archivo del workspace con contenido nuevo."""
            return catalog.write_workspace_file(path=path, content=content, overwrite=overwrite)

        @tool("workspace_run_unix_command")
        def workspace_run_unix_command(command: str, cwd: str = ".", timeout_seconds: int = 120) -> str:
            """Ejecuta un comando Unix en el workspace y devuelve salida estructurada."""
            return catalog._dump_payload(
                catalog.run_unix_command(
                    command=command,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                )
            )

        @tool("workspace_run_mypy")
        def workspace_run_mypy(paths: str = ".", cwd: str = ".") -> str:
            """Ejecuta mypy sobre rutas Python del workspace."""
            return catalog._dump_payload(catalog.run_mypy(paths=paths, cwd=cwd))

        @tool("workspace_run_tests")
        def workspace_run_tests(command: str = "pytest -q", cwd: str = ".") -> str:
            """Ejecuta un comando de pruebas dentro del workspace y devuelve el resultado."""
            return catalog._dump_payload(catalog.run_tests(command=command, cwd=cwd))

        tool_map = {
            "mission_control_blueprint_context": mission_control_blueprint_context,
            "mission_control_delivery_task_context": mission_control_delivery_task_context,
            "mission_control_execution_report": mission_control_execution_report,
            "mission_control_scrum_plan_context": mission_control_scrum_plan_context,
            "mission_control_feedback_digest": mission_control_feedback_digest,
            "mission_control_artifact_digest": mission_control_artifact_digest,
            "workspace_stack_context": workspace_stack_context,
            "workspace_package_manager_context": workspace_package_manager_context,
            "workspace_read_file": workspace_read_file,
            "workspace_write_file": workspace_write_file,
            "workspace_run_unix_command": workspace_run_unix_command,
            "workspace_run_mypy": workspace_run_mypy,
            "workspace_run_tests": workspace_run_tests,
        }
        return [tool_map[spec.name] for spec in selected_specs]

    def get_blueprint_context(self, blueprint_id: int) -> dict[str, Any]:
        blueprint = self._get_blueprint(blueprint_id)
        detail = self.persistence_service.serialize_blueprint_detail(blueprint)
        active_scrum_plan = None
        try:
            active_scrum_plan = self.scrum_planner_service.get_plan_context(blueprint_id)
        except LookupError:
            active_scrum_plan = None
        return {
            "id": detail["id"],
            "project_name": detail["project_name"],
            "capabilities": detail["capabilities"],
            "issues": detail["issues"],
            "summary": detail["summary"],
            "requirements": detail["requirements"][:20],
            "roadmap_epics": detail["roadmap_epics"],
            "active_scrum_plan": active_scrum_plan,
        }

    def get_delivery_task_context(self, *, blueprint_id: int, delivery_task_id: int) -> dict[str, Any]:
        blueprint = self._get_blueprint(blueprint_id)
        for epic in blueprint.delivery_epics:
            for task in epic.delivery_tasks:
                if task.id == delivery_task_id:
                    return {
                        "blueprint_id": blueprint_id,
                        "project_name": blueprint.project_name,
                        "epic": epic.to_dict(),
                        "task": task.to_dict(),
                    }
        raise LookupError("Delivery task not found for blueprint")

    def get_feedback_digest(self, blueprint_id: int) -> dict[str, Any]:
        blueprint = self._get_blueprint(blueprint_id)
        return {
            "blueprint_id": blueprint_id,
            "stage_feedback": [item.to_dict() for item in blueprint.stage_feedback],
            "retrospective_items": [item.to_dict() for item in blueprint.retrospective_items],
        }

    def get_scrum_plan_context(
        self,
        *,
        blueprint_id: int,
        plan_id: int | None = None,
    ) -> dict[str, Any]:
        self._get_blueprint(blueprint_id)
        return self.scrum_planner_service.get_plan_context(blueprint_id, plan_id=plan_id)

    def get_artifact_digest(self, blueprint_id: int) -> dict[str, Any]:
        blueprint = self._get_blueprint(blueprint_id)
        return {
            "blueprint_id": blueprint_id,
            "artifacts": [item.to_dict() for item in blueprint.artifacts],
            "handoffs": [item.to_dict() for item in blueprint.handoffs],
        }

    def detect_workspace_stack(self, *, cwd: str = ".") -> dict[str, Any]:
        resolved_dir = self._resolve_workspace_path(cwd, expect_directory=True)
        ecosystems: list[dict[str, Any]] = []

        python_context = self._detect_python_context(resolved_dir)
        if python_context:
            ecosystems.append(python_context)

        node_context = self._detect_node_context(resolved_dir)
        if node_context:
            ecosystems.append(node_context)

        dotnet_context = self._detect_dotnet_context(resolved_dir)
        if dotnet_context:
            ecosystems.append(dotnet_context)

        cargo_context = self._detect_cargo_context(resolved_dir)
        if cargo_context:
            ecosystems.append(cargo_context)

        go_context = self._detect_go_context(resolved_dir)
        if go_context:
            ecosystems.append(go_context)

        return {
            "workspace_root": str(self.workspace_root),
            "cwd": str(resolved_dir),
            "ecosystems": ecosystems,
        }

    def get_package_manager_context(self, *, ecosystem: str, cwd: str = ".") -> dict[str, Any]:
        normalized = ecosystem.strip().lower()
        stack_context = self.detect_workspace_stack(cwd=cwd)
        aliases = {
            "npm": "node",
            "pnpm": "node",
            "yarn": "node",
            "nuget": "dotnet",
            "dotnet": "dotnet",
            "pip": "python",
            "python": "python",
            "cargo": "cargo",
            "go": "go",
        }
        target = aliases.get(normalized, normalized)
        for item in stack_context["ecosystems"]:
            if item["ecosystem"] == target:
                return item
        raise LookupError(f"Ecosystem not detected in workspace: {ecosystem}")

    def read_workspace_file(self, *, path: str, max_chars: int = 4000) -> str:
        resolved_path = self._resolve_workspace_path(path)
        content = resolved_path.read_text(encoding="utf-8")
        if len(content) > max_chars:
            return content[:max_chars] + "\n...<truncated>"
        return content

    def write_workspace_file(self, *, path: str, content: str, overwrite: bool = True) -> str:
        resolved_path = self._resolve_workspace_path(path)
        if resolved_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {resolved_path}")
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(content, encoding="utf-8")
        return json.dumps(
            {
                "status": "written",
                "path": str(resolved_path),
                "bytes": len(content.encode("utf-8")),
            },
            ensure_ascii=False,
        )

    def run_unix_command(
        self,
        *,
        command: str,
        cwd: str = ".",
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        resolved_dir = self._resolve_workspace_path(cwd, expect_directory=True)
        completed = subprocess.run(
            ["/bin/sh", "-lc", command],
            cwd=resolved_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return self._serialize_process_result(
            command=command,
            cwd=resolved_dir,
            result=completed,
        )

    def run_mypy(self, *, paths: str = ".", cwd: str = ".") -> dict[str, Any]:
        resolved_dir = self._resolve_workspace_path(cwd, expect_directory=True)
        command = [
            "python3",
            "-m",
            "mypy",
            *shlex.split(paths),
        ]
        completed = subprocess.run(
            command,
            cwd=resolved_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return self._serialize_process_result(
            command=" ".join(command),
            cwd=resolved_dir,
            result=completed,
        )

    def run_tests(self, *, command: str = "pytest -q", cwd: str = ".") -> dict[str, Any]:
        return self.run_unix_command(command=command, cwd=cwd, timeout_seconds=240)

    def _get_blueprint(self, blueprint_id: int) -> ProjectBlueprintRecord:
        blueprint = db.session.get(ProjectBlueprintRecord, blueprint_id)
        if blueprint is None:
            raise LookupError("Blueprint not found")
        return blueprint

    def _resolve_workspace_path(self, raw_path: str, *, expect_directory: bool = False) -> Path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        resolved = candidate.resolve()
        if resolved != self.workspace_root and self.workspace_root not in resolved.parents:
            raise ValueError(f"Path escapes workspace root: {raw_path}")
        if expect_directory:
            resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def _serialize_process_result(
        self,
        *,
        command: str,
        cwd: Path,
        result: subprocess.CompletedProcess[str],
    ) -> dict[str, Any]:
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": result.returncode,
            "stdout": self._truncate(result.stdout),
            "stderr": self._truncate(result.stderr),
            "ok": result.returncode == 0,
        }

    @staticmethod
    def _truncate(raw_value: str) -> str:
        if len(raw_value) <= MAX_TOOL_OUTPUT_CHARS:
            return raw_value
        return raw_value[:MAX_TOOL_OUTPUT_CHARS] + "\n...<truncated>"

    @staticmethod
    def _dump_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _detect_python_context(self, root: Path) -> dict[str, Any] | None:
        manifests = []
        if (root / "pyproject.toml").exists():
            manifests.append("pyproject.toml")
        if (root / "requirements.txt").exists():
            manifests.append("requirements.txt")
        if not manifests:
            return None
        return {
            "ecosystem": "python",
            "manifests": manifests,
            "package_manager": "pip",
            "install_command": "python3 -m pip install -r requirements.txt",
            "build_command": "python3 -m compileall .",
            "test_command": "pytest -q",
            "typecheck_command": "python3 -m mypy .",
        }

    def _detect_node_context(self, root: Path) -> dict[str, Any] | None:
        package_json = root / "package.json"
        if not package_json.exists():
            return None
        package_manager = "npm"
        if (root / "pnpm-lock.yaml").exists():
            package_manager = "pnpm"
        elif (root / "yarn.lock").exists():
            package_manager = "yarn"

        scripts: dict[str, Any] = {}
        try:
            scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        except json.JSONDecodeError:
            scripts = {}

        install_command = {
            "pnpm": "pnpm install",
            "yarn": "yarn install",
            "npm": "npm install",
        }[package_manager]
        test_command = scripts.get("test") and f"{package_manager} test" or f"{package_manager} run test"
        build_command = scripts.get("build") and f"{package_manager} run build" or f"{package_manager} run build"
        return {
            "ecosystem": "node",
            "manifests": ["package.json"],
            "package_manager": package_manager,
            "scripts": scripts,
            "install_command": install_command,
            "build_command": build_command,
            "test_command": test_command,
            "typecheck_command": f"{package_manager} run typecheck",
        }

    def _detect_dotnet_context(self, root: Path) -> dict[str, Any] | None:
        sln_files = sorted(root.glob("*.sln"))
        csproj_files = sorted(root.rglob("*.csproj"))
        if not sln_files and not csproj_files:
            return None

        package_refs: list[str] = []
        for csproj_file in csproj_files[:10]:
            try:
                xml_root = ElementTree.fromstring(csproj_file.read_text(encoding="utf-8"))
            except ElementTree.ParseError:
                continue
            for element in xml_root.findall(".//PackageReference"):
                include_value = element.attrib.get("Include")
                if include_value:
                    package_refs.append(include_value)

        manifests = [file.name for file in sln_files[:5]] + [file.name for file in csproj_files[:10]]
        return {
            "ecosystem": "dotnet",
            "manifests": manifests,
            "package_manager": "nuget",
            "install_command": "dotnet restore",
            "build_command": "dotnet build",
            "test_command": "dotnet test",
            "typecheck_command": "dotnet build -warnaserror",
            "package_references": sorted(set(package_refs))[:20],
        }

    def _detect_cargo_context(self, root: Path) -> dict[str, Any] | None:
        if not (root / "Cargo.toml").exists():
            return None
        return {
            "ecosystem": "cargo",
            "manifests": ["Cargo.toml"],
            "package_manager": "cargo",
            "install_command": "cargo fetch",
            "build_command": "cargo build",
            "test_command": "cargo test",
            "typecheck_command": "cargo check",
        }

    def _detect_go_context(self, root: Path) -> dict[str, Any] | None:
        if not (root / "go.mod").exists():
            return None
        return {
            "ecosystem": "go",
            "manifests": ["go.mod"],
            "package_manager": "go",
            "install_command": "go mod download",
            "build_command": "go build ./...",
            "test_command": "go test ./...",
            "typecheck_command": "go test ./...",
        }
