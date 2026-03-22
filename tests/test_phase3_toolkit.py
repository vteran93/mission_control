import importlib
import subprocess
import sys


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
