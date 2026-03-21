import importlib
import sys
from unittest.mock import Mock


def load_agent_api_module():
    sys.modules.pop("agent_api", None)
    return importlib.import_module("agent_api")


def test_infer_agent_role_maps_known_roles():
    agent_api = load_agent_api_module()

    assert agent_api.infer_agent_role("Jarvis-Dev") == "dev"
    assert agent_api.infer_agent_role("Jarvis-QA") == "qa"
    assert agent_api.infer_agent_role("Jarvis-PM") == "pm"
    assert agent_api.infer_agent_role("Victor") == "pm"


def test_mission_control_api_uses_environment_base_url(monkeypatch):
    monkeypatch.setenv("MISSION_CONTROL_API_URL", "http://mission-control:5001/api")
    agent_api = load_agent_api_module()

    existing_agent_response = Mock()
    existing_agent_response.raise_for_status = Mock()
    existing_agent_response.json.return_value = [{"id": 7, "name": "Jarvis-Dev"}]

    get_mock = Mock(return_value=existing_agent_response)
    monkeypatch.setattr(agent_api.requests, "get", get_mock)

    api = agent_api.MissionControlAPI("Jarvis-Dev")

    get_mock.assert_called_once_with("http://mission-control:5001/api/agents")
    assert api.agent_id == 7
