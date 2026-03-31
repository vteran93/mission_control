import importlib
import json
import subprocess
import sys

import pytest

from architecture_guardrails import ArchitectureGuardrailPolicy, save_guardrail_policy
from workspace_markdown_bundle import extract_markdown_file_bundle


def load_modules():
    for module_name in list(sys.modules):
        if module_name == "config" or module_name.startswith("crew_runtime"):
            sys.modules.pop(module_name, None)
    config_module = importlib.import_module("config")
    toolkit_module = importlib.import_module("crew_runtime.toolkit")
    return config_module, toolkit_module


def test_tool_catalog_detects_python_node_and_dotnet_contexts(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"scripts":{"test":"vitest","build":"vite build"}}',
        encoding="utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Demo.csproj").write_text(
        """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Serilog" Version="3.0.0" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("MISSION_CONTROL_BASE_DIR", str(tmp_path))
    config_module, toolkit_module = load_modules()
    settings = config_module.load_settings(base_dir=tmp_path)
    catalog = toolkit_module.RuntimeToolCatalog(settings)

    payload = catalog.detect_workspace_stack(cwd=".")
    ecosystems = {item["ecosystem"]: item for item in payload["ecosystems"]}

    assert "python" in ecosystems
    assert ecosystems["python"]["typecheck_command"] == "python3 -m mypy ."

    assert "node" in ecosystems
    assert ecosystems["node"]["package_manager"] == "pnpm"
    assert ecosystems["node"]["test_command"] == "pnpm test"

    assert "dotnet" in ecosystems
    assert ecosystems["dotnet"]["package_manager"] == "nuget"
    assert "Serilog" in ecosystems["dotnet"]["package_references"]

    assert catalog.get_package_manager_context(ecosystem="npm")["ecosystem"] == "node"
    assert catalog.get_package_manager_context(ecosystem="nuget")["ecosystem"] == "dotnet"


def test_workspace_tools_write_read_unix_and_mypy(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_CONTROL_BASE_DIR", str(tmp_path))
    config_module, toolkit_module = load_modules()
    settings = config_module.load_settings(base_dir=tmp_path)
    catalog = toolkit_module.RuntimeToolCatalog(settings)

    write_result = catalog.write_workspace_file(
        path="generated/example.py",
        content="value = 1\n",
    )
    assert "written" in write_result
    assert catalog.read_workspace_file(path="generated/example.py") == "value = 1\n"

    command_result = catalog.run_unix_command(command="printf 'hello-tools'", cwd=".")
    assert command_result["ok"] is True
    assert command_result["stdout"] == "hello-tools"

    def fake_run(command, cwd, capture_output, text, timeout):
        assert command == ["python3", "-m", "mypy", "generated/example.py"]
        assert cwd == tmp_path
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="Success: no issues found\n",
            stderr="",
        )

    monkeypatch.setattr(toolkit_module.subprocess, "run", fake_run)
    mypy_result = catalog.run_mypy(paths="generated/example.py", cwd=".")

    assert mypy_result["ok"] is True
    assert "no issues found" in mypy_result["stdout"]


def test_workspace_tools_respect_architecture_guardrails(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_CONTROL_BASE_DIR", str(tmp_path))
    config_module, toolkit_module = load_modules()
    settings = config_module.load_settings(base_dir=tmp_path)
    catalog = toolkit_module.RuntimeToolCatalog(settings)

    save_guardrail_policy(
        tmp_path,
        ArchitectureGuardrailPolicy.from_dict(
            {
                "scope": {"kind": "test"},
                "allowed_write_paths": ["allowed/output.txt"],
                "allowed_write_roots": [".mission_control/reports/"],
            }
        ),
    )

    write_result = catalog.write_workspace_file(
        path="allowed/output.txt",
        content="ok\n",
    )
    assert "written" in write_result

    with pytest.raises(ValueError, match="architecture guardrails"):
        catalog.write_workspace_file(
            path=".git/config",
            content="[core]\nrepositoryformatversion = 0\n",
        )

    with pytest.raises(ValueError, match="Command blocked by runtime guardrails"):
        catalog.run_unix_command(command="rm -rf allowed", cwd=".")


def test_extract_markdown_file_bundle_supports_multiple_comment_styles():
    files = extract_markdown_file_bundle(
        """```python
# filepath: generated/example.py
print("hola")
```

```ts
// filepath: frontend/src/index.ts
console.log("hola")
```

```html
<!-- filepath: frontend/index.html -->
<div>hola</div>
```
"""
    )

    assert [item.path for item in files] == [
        "generated/example.py",
        "frontend/src/index.ts",
        "frontend/index.html",
    ]
    assert [item.language for item in files] == ["python", "ts", "html"]


def test_workspace_apply_markdown_bundle_writes_files_and_respects_guardrails(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_CONTROL_BASE_DIR", str(tmp_path))
    config_module, toolkit_module = load_modules()
    settings = config_module.load_settings(base_dir=tmp_path)
    catalog = toolkit_module.RuntimeToolCatalog(settings)

    payload = catalog.apply_markdown_bundle(
        bundle_markdown="""```python
# filepath: generated/example.py
print("hola")
```

```json
// filepath: frontend/package.json
{"name":"demo"}
```
""",
    )

    assert payload["status"] == "written"
    assert payload["file_count"] == 2
    assert json.loads((tmp_path / "frontend" / "package.json").read_text(encoding="utf-8")) == {
        "name": "demo"
    }
    assert (tmp_path / "generated" / "example.py").read_text(encoding="utf-8") == 'print("hola")'

    save_guardrail_policy(
        tmp_path,
        ArchitectureGuardrailPolicy.from_dict(
            {
                "scope": {"kind": "test"},
                "allowed_write_paths": ["allowed/output.txt"],
                "allowed_write_roots": [".mission_control/reports/"],
            }
        ),
    )

    with pytest.raises(ValueError, match="architecture guardrails"):
        catalog.apply_markdown_bundle(
            bundle_markdown="""```ini
# filepath: .git/config
[core]
repositoryformatversion = 0
```
"""
        )
