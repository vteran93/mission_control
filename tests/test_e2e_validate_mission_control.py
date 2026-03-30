import argparse
import importlib.util
import sys
from pathlib import Path

import pytest


def load_script_module():
    module_name = "scripts.e2e_validate_mission_control_test"
    sys.modules.pop(module_name, None)
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "e2e_validate_mission_control.py"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def make_args(**overrides):
    defaults = {
        "requirements_path": None,
        "roadmap_path": None,
        "project_root": None,
        "input_artifact": [],
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_resolve_external_phase4_specs_supports_formal_pair(tmp_path):
    script = load_script_module()
    requirements_path = tmp_path / "requirements.md"
    roadmap_path = tmp_path / "roadmap.md"
    requirements_path.write_text("# Requirements\n", encoding="utf-8")
    roadmap_path.write_text("# Roadmap\n", encoding="utf-8")

    source = script.resolve_external_phase4_specs(
        make_args(
            requirements_path=str(requirements_path),
            roadmap_path=str(roadmap_path),
        )
    )

    assert source is not None
    assert source.input_mode == "formal_pair"
    assert source.import_payload == {
        "requirements_path": str(requirements_path.resolve()),
        "roadmap_path": str(roadmap_path.resolve()),
    }
    assert source.artifact_paths == (requirements_path.resolve(), roadmap_path.resolve())


def test_resolve_external_phase4_specs_supports_project_root_dossier(tmp_path):
    script = load_script_module()
    dossier_root = tmp_path / "example_project_2"
    dossier_root.mkdir()
    roadmap_path = dossier_root / "VEO3_CLAUDE_INTEGRATION_ROADMAP.md"
    diagram_path = dossier_root / "AGENTIC_WORKFLOW_CLASS_DIAGRAM.md"
    roadmap_path.write_text("# Roadmap\n## Fase 0. Setup\n", encoding="utf-8")
    diagram_path.write_text("# Diagram\n## Decision de arquitectura\n", encoding="utf-8")

    source = script.resolve_external_phase4_specs(
        make_args(project_root=str(dossier_root))
    )

    assert source is not None
    assert source.input_mode == "input_artifacts"
    assert source.project_label == dossier_root.name
    assert source.import_payload == {
        "input_artifacts": [
            str(diagram_path.resolve()),
            str(roadmap_path.resolve()),
        ]
    }
    assert source.artifact_paths == (diagram_path.resolve(), roadmap_path.resolve())


def test_resolve_external_phase4_specs_supports_input_artifacts_list(tmp_path):
    script = load_script_module()
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    brief_path = artifact_dir / "brief.md"
    notes_path = artifact_dir / "notes.md"
    brief_path.write_text("# Brief\n", encoding="utf-8")
    notes_path.write_text("# Notes\n", encoding="utf-8")

    source = script.resolve_external_phase4_specs(
        make_args(input_artifact=[str(brief_path), str(notes_path)])
    )

    assert source is not None
    assert source.input_mode == "input_artifacts"
    assert source.project_label == artifact_dir.name
    assert source.import_payload == {
        "input_artifacts": [
            str(brief_path.resolve()),
            str(notes_path.resolve()),
        ]
    }
    assert source.artifact_paths == (brief_path.resolve(), notes_path.resolve())


def test_resolve_external_phase4_specs_rejects_mixed_modes(tmp_path):
    script = load_script_module()
    requirements_path = tmp_path / "requirements.md"
    requirements_path.write_text("# Requirements\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Use only one external Phase 4 input mode"):
        script.resolve_external_phase4_specs(
            make_args(
                project_root=str(tmp_path),
                input_artifact=[str(requirements_path)],
            )
        )


def test_import_blueprint_uses_generic_payload(monkeypatch):
    script = load_script_module()
    captured = {}

    def fake_api_call(base_url, method, path, payload=None):
        captured["base_url"] = base_url
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        return 201, {"id": 7}

    monkeypatch.setattr(script, "api_call", fake_api_call)

    payload = {"input_artifacts": ["/tmp/brief.md", "/tmp/roadmap.md"]}
    response = script.import_blueprint("http://127.0.0.1:5001", payload)

    assert response == {"id": 7}
    assert captured == {
        "base_url": "http://127.0.0.1:5001",
        "method": "POST",
        "path": "/api/blueprints/import",
        "payload": payload,
    }
