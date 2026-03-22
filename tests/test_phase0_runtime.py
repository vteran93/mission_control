import importlib
import sys


def load_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_load_settings_reads_agentic_runtime_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_CONTROL_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("MISSION_CONTROL_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_AUTOSTART", "true")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_BATCH_SIZE", "7")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_EXECUTOR", "legacy_bridge")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_RECOVER_AFTER_SECONDS", "321")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_ESCALATE_AFTER_RETRIES", "2")
    monkeypatch.setenv("MISSION_CONTROL_DISPATCHER_ENABLE_FALLBACK", "false")
    monkeypatch.setenv("MISSION_CONTROL_ENABLE_LEGACY_BRIDGE", "true")
    monkeypatch.setenv("MISSION_CONTROL_LEGACY_GATEWAY_URL", "http://gateway:9999")
    monkeypatch.setenv("MISSION_CONTROL_LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("MISSION_CONTROL_LLM_MAX_TOKENS", "1024")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:latest")
    monkeypatch.setenv("BEDROCK_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_PLANNER_MODEL", "anthropic.claude-3-7-sonnet")
    monkeypatch.setenv("BEDROCK_REVIEWER_MODEL", "anthropic.claude-3-5-sonnet")
    monkeypatch.setenv("GITHUB_API_URL", "https://github.enterprise.local/api/v3")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/mission-control")
    monkeypatch.setenv("GITHUB_DEFAULT_BASE_BRANCH", "develop")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

    config = load_module("config")
    settings = config.load_settings()

    assert settings.runtime.enabled is True
    assert settings.runtime.dispatcher_autostart is True
    assert settings.runtime.dispatcher_batch_size == 7
    assert settings.runtime.dispatcher_executor == "legacy_bridge"
    assert settings.runtime.dispatcher_recover_after_seconds == 321
    assert settings.runtime.dispatcher_escalate_after_retries == 2
    assert settings.runtime.dispatcher_enable_fallback is False
    assert settings.runtime.llm_timeout_seconds == 45
    assert settings.runtime.llm_max_tokens == 1024
    assert settings.runtime.enable_legacy_bridge is True
    assert settings.runtime.legacy_gateway_url == "http://gateway:9999"
    assert settings.ollama.base_url == "http://ollama:11434"
    assert settings.ollama.default_model == "qwen2.5-coder:latest"
    assert settings.bedrock.region == "us-east-1"
    assert settings.bedrock.planner_model == "anthropic.claude-3-7-sonnet"
    assert settings.bedrock.reviewer_model == "anthropic.claude-3-5-sonnet"
    assert settings.github.api_url == "https://github.enterprise.local/api/v3"
    assert settings.github.repository == "acme/mission-control"
    assert settings.github.default_base_branch == "develop"
