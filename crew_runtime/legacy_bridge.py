from __future__ import annotations

import requests

from .contracts import DispatchResult, DispatchTask


def build_legacy_prompt(task: DispatchTask) -> str:
    return f"""[MISSION CONTROL WORK]

Message ID: {task.message_id}
From: {task.from_agent}
Priority: {task.priority}

{task.content}

---

YOUR IDENTITY: {task.target_agent.title().replace('-', ' ')}

ACTION: Execute the work described above. Do not stop at acknowledgement.
"""


class LegacyGatewayExecutor:
    """Compatibility adapter for the legacy Gateway path.

    This stays off the main path and is only enabled explicitly.
    """

    name = "legacy_gateway_bridge"

    def __init__(self, gateway_url: str, gateway_token: str | None):
        self.gateway_url = gateway_url.rstrip("/")
        self.gateway_token = gateway_token

    def dispatch(self, task: DispatchTask) -> DispatchResult:
        if not self.gateway_token:
            return DispatchResult(
                queue_id=task.queue_id,
                success=False,
                detail="CLAWDBOT_GATEWAY_TOKEN no configurado",
                runtime_name=self.name,
            )

        payload = {
            "tool": "sessions_spawn",
            "args": {
                "label": task.target_agent,
                "task": build_legacy_prompt(task),
                "cleanup": "keep",
                "runTimeoutSeconds": 7200,
            },
        }

        try:
            response = requests.post(
                f"{self.gateway_url}/tools/invoke",
                headers={
                    "Authorization": f"Bearer {self.gateway_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            return DispatchResult(
                queue_id=task.queue_id,
                success=False,
                detail=f"Legacy gateway error: {exc}",
                runtime_name=self.name,
            )

        ok = result.get("ok", False)
        details = result.get("result", {}).get("details", {})
        return DispatchResult(
            queue_id=task.queue_id,
            success=ok,
            detail="Legacy gateway dispatch completado" if ok else result.get("error", {}).get("message", "Legacy gateway fallo"),
            runtime_name=self.name,
            external_ref=details.get("childSessionKey"),
        )
