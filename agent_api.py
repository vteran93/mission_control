import os
from typing import Optional

import requests


def infer_agent_role(agent_name: str) -> str:
    lowered = agent_name.lower()
    if "dev" in lowered:
        return "dev"
    if "qa" in lowered:
        return "qa"
    if "pm" in lowered or "victor" in lowered:
        return "pm"
    return "dev"


class MissionControlAPI:
    """Cliente Python para que agentes escriban a Mission Control."""

    def __init__(
        self,
        agent_name: str,
        base_url: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.base_url = base_url or os.getenv(
            "MISSION_CONTROL_API_URL",
            "http://localhost:5001/api",
        )
        self.agent_id = self._get_or_create_agent()

    def _get_or_create_agent(self) -> int:
        response = requests.get(f"{self.base_url}/agents")
        response.raise_for_status()
        agents = response.json()

        for agent in agents:
            if agent["name"] == self.agent_name:
                return agent["id"]

        response = requests.post(
            f"{self.base_url}/agents",
            json={
                "name": self.agent_name,
                "role": infer_agent_role(self.agent_name),
                "status": "idle",
            },
        )
        response.raise_for_status()
        return response.json()["id"]

    def update_status(self, status: str) -> None:
        requests.put(
            f"{self.base_url}/agents/{self.agent_id}",
            json={"status": status, "last_seen_at": True},
        ).raise_for_status()
        print(f"✅ {self.agent_name} status → {status}")

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        status: str = "todo",
        assignee_agent_ids: str = "",
    ) -> int:
        response = requests.post(
            f"{self.base_url}/tasks",
            json={
                "title": title,
                "description": description,
                "status": status,
                "priority": priority,
                "assignee_agent_ids": assignee_agent_ids or str(self.agent_id),
                "created_by": self.agent_name,
            },
        )
        response.raise_for_status()
        task_id = response.json()["id"]
        print(f"✅ Task #{task_id} creada: {title}")
        return task_id

    def update_task(
        self,
        task_id: int,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> None:
        payload = {}
        if status:
            payload["status"] = status
        if assignee:
            payload["assignee_agent_ids"] = assignee
        if priority:
            payload["priority"] = priority

        requests.put(f"{self.base_url}/tasks/{task_id}", json=payload).raise_for_status()
        print(f"✅ Task #{task_id} actualizada: {payload}")

    def send_message(self, content: str, task_id: Optional[int] = None) -> None:
        requests.post(
            f"{self.base_url}/messages",
            json={"task_id": task_id, "from_agent": self.agent_name, "content": content},
        ).raise_for_status()
        print(f"💬 {self.agent_name}: {content[:50]}...")

    def create_document(
        self,
        title: str,
        content_md: str,
        doc_type: str = "code",
        task_id: Optional[int] = None,
    ) -> int:
        response = requests.post(
            f"{self.base_url}/documents",
            json={
                "title": title,
                "content_md": content_md,
                "type": doc_type,
                "task_id": task_id,
            },
        )
        response.raise_for_status()
        doc_id = response.json()["id"]
        print(f"📄 Documento #{doc_id} creado: {title}")
        return doc_id

    def notify_scrum_master(self, message: str) -> None:
        requests.post(
            f"{self.base_url}/notifications",
            json={"agent_id": None, "content": f"[{self.agent_name}] {message}"},
        ).raise_for_status()
        print(f"🔔 Notificación enviada: {message}")

    def send_message_to_agent(
        self,
        target_agent: str,
        message: str,
        task_id: Optional[int] = None,
        priority: str = "normal",
    ) -> dict:
        label_map = {
            "Jarvis-QA": "jarvis-qa",
            "Jarvis-Dev": "jarvis-dev",
            "Jarvis-PM": "jarvis-pm",
            "jarvis-qa": "jarvis-qa",
            "jarvis-dev": "jarvis-dev",
            "jarvis-pm": "jarvis-pm",
        }

        label = label_map.get(target_agent, target_agent.lower())

        response = requests.post(
            f"{self.base_url}/send-agent-message",
            json={
                "target_agent": label,
                "message": message,
                "task_id": task_id,
                "from_agent": self.agent_name,
                "priority": priority,
            },
        )
        response.raise_for_status()
        queued = response.json()
        queued["label"] = label
        print(f"📨 Mensaje para {target_agent} encolado: {queued.get('message_id')}")
        return queued
