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


def test_send_message_to_agent_calls_queue_endpoint(monkeypatch):
    monkeypatch.setenv("MISSION_CONTROL_API_URL", "http://mission-control:5001/api")
    agent_api = load_agent_api_module()

    existing_agent_response = Mock()
    existing_agent_response.raise_for_status = Mock()
    existing_agent_response.json.return_value = [{"id": 7, "name": "Jarvis-Dev"}]

    queued_response = Mock()
    queued_response.raise_for_status = Mock()
    queued_response.json.return_value = {"status": "queued", "message_id": "12"}

    monkeypatch.setattr(agent_api.requests, "get", Mock(return_value=existing_agent_response))
    post_mock = Mock(return_value=queued_response)
    monkeypatch.setattr(agent_api.requests, "post", post_mock)

    api = agent_api.MissionControlAPI("Jarvis-Dev")
    api.send_message = Mock()

    payload = api.send_message_to_agent("Jarvis-QA", "Revisa este cambio", task_id=9, priority="high")

    post_mock.assert_called_once_with(
        "http://mission-control:5001/api/send-agent-message",
        json={
            "target_agent": "jarvis-qa",
            "message": "Revisa este cambio",
            "task_id": 9,
            "from_agent": "Jarvis-Dev",
            "priority": "high",
        },
    )
    assert payload["status"] == "queued"
    assert payload["label"] == "jarvis-qa"
