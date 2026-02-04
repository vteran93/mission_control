# OpenClaw LangGraph Orchestrator

Production-grade Supervisor-Worker orchestration layer that treats LangGraph as the **Prefrontal Cortex** (logic/state) and OpenClaw as the **Motor System** (execution/tools). The bridge reads `.openclaw/state/latest_run.json` so agents never need to re-explain work.

## Configuration

### `OPENCLAW_STATE_DIR`

Set the environment variable to the directory where OpenClaw persists state (the folder that contains `latest_run.json`). Example:

```bash
export OPENCLAW_STATE_DIR="$HOME/.openclaw/state"
```

### `OPENCLAW_SQLITE_PATH`

Optional: override the checkpoint path for LangGraph persistence:

```bash
export OPENCLAW_SQLITE_PATH="$HOME/.openclaw/state/orchestrator.sqlite"
```

## Running the Orchestrator

```python
from openclaw_orchestrator import OpenClawBridge, build_app

bridge = OpenClawBridge()
app = build_app(bridge)

initial_state = {
    "ticket_id": "TICKET-401",
    "requirements": "Implement the OpenClaw/LangGraph bridge",
    "disk_checkpoint": "",
    "code_diff": "",
    "revision_count": 0,
    "next_step": "developer",
}

app.invoke(initial_state)
```

## Token Savings Report

The orchestrator reads diffs and terminal output from disk instead of asking the LLM to summarize past work.

**Formula**

```
Savings % = (1 - (DiskTokens / PromptTokens)) * 100
```

- `PromptTokens`: tokens required to re-send full conversation/history to an agent.
- `DiskTokens`: tokens required to inject just `requirements` + `code_diff`.

**Example**

If history costs 12,000 tokens and the disk diff costs 1,500 tokens:

```
Savings % = (1 - (1500 / 12000)) * 100 = 87.5%
```

The QA node is hard-limited to `requirements` and `code_diff`, guaranteeing token-efficient validation.

## Skill Registration

```python
from openclaw_orchestrator.skill import register_skill

# The registry callback is provided by ClawHub/OpenClaw runtime.
register_skill(registry_callback)
```
