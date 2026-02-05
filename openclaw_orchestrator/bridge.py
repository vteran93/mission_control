"""Bridge between LangGraph state and OpenClaw local persistence."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class OpenClawSnapshot:
    """Snapshot extracted from OpenClaw's local state files."""

    disk_checkpoint: str
    last_terminal_output: str
    filesystem_diffs: str


class OpenClawBridge:
    """Parse OpenClaw state and dispatch commands to agent runtimes."""

    def __init__(
        self,
        state_dir: str | None = None,
        dispatcher: Callable[[str, str], Mapping[str, Any]] | None = None,
    ) -> None:
        self._state_dir = state_dir or os.environ.get(
            "OPENCLAW_STATE_DIR", os.path.join(".openclaw", "state")
        )
        self._dispatcher = dispatcher

    @property
    def latest_run_path(self) -> str:
        """Return the absolute path to the latest OpenClaw run JSON."""

        return os.path.join(self._state_dir, "latest_run.json")

    @property
    def state_dir(self) -> str:
        """Return the configured OpenClaw state directory."""

        return self._state_dir

    def load_latest_run(self) -> Mapping[str, Any]:
        """Load the latest run JSON from disk."""

        with open(self.latest_run_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def snapshot(self) -> OpenClawSnapshot:
        """Extract a snapshot of the latest OpenClaw run."""

        latest = self.load_latest_run()
        return OpenClawSnapshot(
            disk_checkpoint=self.latest_run_path,
            last_terminal_output=str(latest.get("last_terminal_output", "")),
            filesystem_diffs=str(latest.get("filesystem_diffs", "")),
        )

    def dispatch_to_claw(self, agent_role: str, command: str) -> Mapping[str, Any]:
        """Dispatch a command to an OpenClaw agent role.

        The default behavior shells out locally. Inject a dispatcher for
        ClawHub/OpenClawTool integrations.
        """

        if self._dispatcher is not None:
            return self._dispatcher(agent_role, command)

        result = subprocess.run(
            command, shell=True, check=False, capture_output=True, text=True
        )
        return {
            "agent_role": agent_role,
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
