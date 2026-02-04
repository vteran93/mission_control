# How to Create a New Agent in Clawdbot + Mission Control

**Last Updated:** 2026-02-03  
**Author:** Jarvis (Project Owner)

---

## Overview

This guide documents the process for creating a new specialized agent that integrates with Mission Control API and Clawdbot's agent system.

**Example:** Creation of `Jarvis-Frontend` (React/Vue/UI/UX specialist)

---

## Prerequisites

- Mission Control API running (`http://localhost:5001`)
- Access to Clawdbot workspace (`~/clawd/`)
- SQLite access to Mission Control database

---

## Step-by-Step Process

### 1. Add Agent to Mission Control Database

**Connect to SQLite database:**

```bash
cd ~/repositories/mission_control
sqlite3 instance/mission_control.db
```

**Check table schema first:**

```sql
PRAGMA table_info(agents);
```

**Output:**
```
0|id|INTEGER|1||1
1|name|VARCHAR(100)|1||0
2|role|VARCHAR(50)|1||0
3|session_key|VARCHAR(200)|0||0
4|status|VARCHAR(50)|0||0
5|last_seen_at|DATETIME|0||0
```

**Insert new agent:**

```sql
INSERT INTO agents (name, role, status)
VALUES ('Jarvis-Frontend', 'Frontend Developer | React | Vue | UI/UX', 'active');
```

**Verify insertion:**

```sql
SELECT id, name, role, status FROM agents WHERE name = 'Jarvis-Frontend';
```

**Output:**
```
3|Jarvis-Frontend|Frontend Developer | React | Vue | UI/UX|active
```

**Alternative: Python script**

```python
import sqlite3

conn = sqlite3.connect('instance/mission_control.db')
c = conn.cursor()

# Insert new agent
c.execute("""
    INSERT INTO agents (name, role, status)
    VALUES ('Jarvis-Frontend', 'Frontend Developer | React | Vue | UI/UX', 'active')
""")

conn.commit()
agent_id = c.lastrowid

print(f"✅ Agent created: ID={agent_id}, name=Jarvis-Frontend")

# Verify
c.execute("SELECT id, name, role, status FROM agents WHERE name = 'Jarvis-Frontend'")
agent = c.fetchone()
print(f"📋 Agent: id={agent[0]}, name={agent[1]}, role={agent[2]}, status={agent[3]}")

conn.close()
```

**Run:**
```bash
cd ~/repositories/mission_control
python3 create_agent.py
```

---

### 2. Create Agent Workspace in Clawdbot

**Directory structure:**

```bash
mkdir -p ~/clawd/agents/jarvis-frontend/memory
```

**Files to create:**

```
~/clawd/agents/jarvis-frontend/
├── IDENTITY.md      # Core identity, specializations, personality
├── AGENTS.md        # Workflow, tools, anti-patterns
├── USER.md          # Reference to Victor (user info)
└── memory/          # Daily memory logs
    └── YYYY-MM-DD.md
```

---

### 3. Write IDENTITY.md

**Template:**

```markdown
# IDENTITY.md - {Agent-Name}

- **Name:** {Agent-Name}
- **Creature:** {Role Description}
- **Vibe:** {Personality traits}
- **Emoji:** {Emoji}
- **Avatar:** N/A

---

## Core Role

I am **{Agent-Name}**, the **{Role}** of the Jarvis team with the following credentials:
- {Credential 1}
- {Credential 2}
- {Credential 3}

**Specializations:**
- {Specialization 1}
- {Specialization 2}
- {Specialization 3}

My function is **{primary responsibility}**.

---

## Personality

{Describe personality traits, work style, values}

---

## Communication Style

**With Victor (only exception):**
- **Channel:** Webchat direct (if assigned)
- **Language:** Spanish by default
- **Tone:** {Conversational/Formal/etc}
- **Format:** {Preferred format}

**With agents:**
- **Channel:** Mission Control API (mandatory)
- **Language:** Spanish (mandatory)
- **Format:** {Clear, with examples}
- **Prohibited:** Direct `sessions_send` between agents

---

## Decision-Making Framework

{How this agent makes decisions}

---

## Responsibilities

{List of key responsibilities}

---

## Anti-Patterns (What NOT to do)

❌ {Anti-pattern 1}
❌ {Anti-pattern 2}

✅ {What to DO instead}

---

*Updated: YYYY-MM-DD - Creation*
```

**Example for Jarvis-Frontend:**

See: `~/clawd/agents/jarvis-frontend/IDENTITY.md`

---

### 4. Write AGENTS.md

**Template:**

```markdown
# AGENTS.md - {Agent-Name} Workspace

This folder is my home as {Agent-Name}.

## Session Startup

Every session:
1. Read `IDENTITY.md` - Who I am
2. Read `USER.md` - Who I work with
3. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context
4. **DO NOT read MEMORY.md** - That's only for Jarvis main session

## Memory

- **Daily notes:** `memory/YYYY-MM-DD.md` - Logs of my work
- **NO MEMORY.md** - Only for Jarvis main

## Mission Control

**Communication with other agents:**
- Use Mission Control API: `http://localhost:5001/api/messages`
- POST messages with `from_agent: "{agent-name}"`
- **Prohibited:** Direct `sessions_send`

**When assigned work:**
- Receive message via Mission Control
- Read ticket/requirement
- Implement {task type}
- Report progress/completion

## Tools

I have access to:
- `read`, `write`, `edit` - For code
- `exec` - For {relevant commands}
- {Other tools relevant to this agent}

## Anti-Patterns

❌ Don't create sub-agents
❌ Don't talk directly to Victor (unless mentioned)
❌ Don't make product decisions (escalate to Jarvis PO)

✅ Do {primary responsibilities}
✅ Do propose improvements
✅ Do report blockers immediately

---

**Ready to receive {task type} tickets.** {emoji}
```

---

### 5. Write USER.md

**Simple reference:**

```markdown
# USER.md - About Victor

(Same as Jarvis main - Victor is the Project Owner, only direct communication channel)

See: `/home/victor/clawd/USER.md`
```

---

### 6. Verify Mission Control API

**Test the API endpoint:**

```bash
curl -s http://localhost:5001/api/agents | jq
```

**Expected output:**

```json
[
  {
    "id": 1,
    "name": "Jarvis-Dev",
    "role": "dev",
    "status": "idle"
  },
  {
    "id": 2,
    "name": "Jarvis-QA",
    "role": "qa",
    "status": "idle"
  },
  {
    "id": 3,
    "name": "Jarvis-Frontend",
    "role": "Frontend Developer | React | Vue | UI/UX",
    "status": "active"
  }
]
```

---

### 7. Document Agent Profile in Mission Control

**Create agent profile document:**

```bash
# In Mission Control repo
touch ~/repositories/mission_control/docs/AGENT_{AGENT_NAME}.md
```

**Content:**

```markdown
# {Agent-Name} - Agent Profile

**Created:** YYYY-MM-DD
**Status:** Active
**Mission Control ID:** {id}

---

## Core Identity

- **Name:** {Agent-Name}
- **Role:** {Role}
- **Emoji:** {Emoji}
- **Vibe:** {Personality}

---

## Specializations

{List of specializations with descriptions}

---

## Tech Stack Preferences

{Tools, frameworks, libraries this agent prefers}

---

## Personality

{Personality traits and work style}

---

## Communication Style

{How this agent communicates}

---

## Responsibilities

{Key responsibilities}

---

## Workflow

{How this agent works on tickets}

---

## Anti-Patterns

{What NOT to do}

---

## Example Work

{Code examples or work samples}

---

## Collaboration

{How this agent collaborates with others}

---

## Workspace Location

**Clawdbot Agent Directory:** `~/clawd/agents/{agent-name}/`

---

## Mission Control Integration

**Database Entry:**
- **Table:** `agents`
- **ID:** {id}
- **Name:** `{Agent-Name}`
- **Role:** `{Role}`
- **Status:** `active`

---

## Activation

To spawn {Agent-Name} for a task:

```python
sessions_spawn(
    label="{agent-name}",
    task="[TICKET-XXX] {Task description}",
    cleanup="keep"
)
```

---

**Status:** ✅ Active and ready for {task type} tickets
**Created by:** Jarvis (Project Owner)
**Date:** YYYY-MM-DD
```

**Example:**

See: `~/repositories/mission_control/docs/AGENT_JARVIS_FRONTEND.md`

---

### 8. Commit Changes

**In Clawdbot workspace:**

```bash
cd ~/clawd
git add agents/{agent-name}/
git commit -m "Add {Agent-Name} agent: {brief description}"
git push origin main
```

**In Mission Control repo:**

```bash
cd ~/repositories/mission_control
git add docs/AGENT_{AGENT_NAME}.md
git commit -m "docs: Add {Agent-Name} agent profile"
git push origin main
```

---

## Testing the New Agent

### 1. Spawn the agent via Clawdbot

```python
sessions_spawn(
    label="jarvis-frontend",
    task="[TEST] Verify agent identity and workspace. Report back your specializations.",
    cleanup="keep"
)
```

### 2. Send message via Mission Control API

```bash
curl -X POST http://localhost:5001/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "from_agent": "Jarvis",
    "to_agent": "jarvis-frontend",
    "content": "[TEST] Hello! Confirm you received this message."
  }'
```

### 3. Verify agent can read Mission Control messages

The agent should:
1. Poll Mission Control API for messages
2. Read assigned tasks from database
3. Report back via Mission Control API

---

## Agent Naming Conventions

### Database (`name` field)
- **Format:** `Jarvis-{Specialization}` (PascalCase with hyphen)
- **Examples:**
  - `Jarvis-Dev`
  - `Jarvis-Frontend`
  - `Jarvis-QA`
  - `Jarvis-PM`

### Clawdbot Label (`sessions_spawn` label)
- **Format:** `jarvis-{specialization}` (lowercase with hyphen)
- **Examples:**
  - `jarvis-dev`
  - `jarvis-frontend`
  - `jarvis-qa`
  - `jarvis-pm`

### Workspace Directory
- **Format:** `jarvis-{specialization}` (lowercase with hyphen)
- **Path:** `~/clawd/agents/jarvis-{specialization}/`

---

## Agent Communication Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Jarvis (PO)                          │
│              Project Owner / Coordinator                │
└──────────────┬──────────────────────────────────────────┘
               │
               │ POST /api/messages
               │ {from: "Jarvis", to: "jarvis-frontend", ...}
               ▼
┌─────────────────────────────────────────────────────────┐
│              Mission Control API                         │
│         http://localhost:5001/api/messages              │
└──────────────┬──────────────────────────────────────────┘
               │
               │ Stores in task_queue table
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│        Jarvis (PO) - Heartbeat Processor                │
│   Reads task_queue → spawns agent with sessions_spawn   │
└──────────────┬──────────────────────────────────────────┘
               │
               │ sessions_spawn(label="jarvis-frontend", task="...")
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│            Jarvis-Frontend (Sub-Agent)                  │
│       Reads IDENTITY.md, executes work, reports         │
└──────────────┬──────────────────────────────────────────┘
               │
               │ POST /api/messages
               │ {from: "Jarvis-Frontend", content: "[COMPLETED] ..."}
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│              Mission Control API                         │
│            Stores completion report                      │
└─────────────────────────────────────────────────────────┘
```

---

## Checklist for New Agent Creation

- [ ] **Step 1:** Add agent to Mission Control database
  - [ ] Verify table schema
  - [ ] Insert agent record
  - [ ] Verify with SELECT query
- [ ] **Step 2:** Create agent workspace in `~/clawd/agents/`
  - [ ] Create directory structure
  - [ ] Create `memory/` subdirectory
- [ ] **Step 3:** Write `IDENTITY.md`
  - [ ] Core role and specializations
  - [ ] Personality traits
  - [ ] Communication style
  - [ ] Decision-making framework
  - [ ] Responsibilities
  - [ ] Anti-patterns
- [ ] **Step 4:** Write `AGENTS.md`
  - [ ] Session startup instructions
  - [ ] Memory management
  - [ ] Mission Control integration
  - [ ] Tools available
  - [ ] Anti-patterns
- [ ] **Step 5:** Write `USER.md`
  - [ ] Reference to main USER.md
- [ ] **Step 6:** Verify Mission Control API
  - [ ] `curl http://localhost:5001/api/agents`
  - [ ] Agent appears in list
- [ ] **Step 7:** Document agent profile
  - [ ] Create `AGENT_{NAME}.md` in Mission Control docs
  - [ ] Include all sections from template
- [ ] **Step 8:** Commit changes
  - [ ] Commit to `~/clawd/` (Clawdbot)
  - [ ] Commit to Mission Control repo
  - [ ] Push to main (both repos)
- [ ] **Step 9:** Test the agent
  - [ ] Spawn via `sessions_spawn`
  - [ ] Send test message via API
  - [ ] Verify agent can read/respond

---

## Example: Jarvis-Frontend Creation Summary

**Date:** 2026-02-03

**Database:**
```sql
INSERT INTO agents (name, role, status)
VALUES ('Jarvis-Frontend', 'Frontend Developer | React | Vue | UI/UX', 'active');
-- Result: ID=3
```

**Workspace:**
```
~/clawd/agents/jarvis-frontend/
├── IDENTITY.md      (8922 bytes)
├── AGENTS.md        (1379 bytes)
├── USER.md          (149 bytes)
└── memory/          (empty)
```

**Documentation:**
```
~/repositories/mission_control/docs/AGENT_JARVIS_FRONTEND.md
(9717 bytes)
```

**Commits:**
- Clawdbot: `13ee883` - "Add Jarvis-Frontend agent: React/Vue/UI/UX specialist"
- Mission Control: (pending) - "docs: Add Jarvis-Frontend agent profile and creation guide"

**Verification:**
```bash
curl -s http://localhost:5001/api/agents | jq '.[] | select(.name=="Jarvis-Frontend")'
# Output: {"id":3,"name":"Jarvis-Frontend","role":"Frontend Developer | React | Vue | UI/UX","status":"active"}
```

---

## Troubleshooting

### Agent doesn't appear in API

**Check database:**
```sql
SELECT * FROM agents WHERE name = '{Agent-Name}';
```

**Restart Mission Control API:**
```bash
cd ~/repositories/mission_control
docker-compose restart api
```

### Agent can't read workspace files

**Verify permissions:**
```bash
ls -la ~/clawd/agents/{agent-name}/
```

**Check file contents:**
```bash
cat ~/clawd/agents/{agent-name}/IDENTITY.md
```

### Agent doesn't spawn

**Check label format:**
```python
# Correct:
sessions_spawn(label="jarvis-frontend", task="...")

# Wrong:
sessions_spawn(label="Jarvis-Frontend", task="...")  # PascalCase won't work
```

---

## Future Improvements

- [ ] Automated agent creation script (`scripts/create_agent.sh`)
- [ ] Agent template repository
- [ ] Web UI for agent creation in Mission Control
- [ ] Agent capability discovery (list available skills)
- [ ] Agent load balancing (distribute work across instances)

---

**Author:** Jarvis (Project Owner)  
**Version:** 1.0  
**Last Updated:** 2026-02-03
