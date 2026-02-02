# Mission Control - Architecture & Cost Optimization

## 🎯 Purpose

Coordination system for AI agent team working on software projects.

**Critical Constraint:** Budget = $50 USD (Victor's 5-day salary)  
**Goal:** Prove agents can 10x productivity cost-effectively

---

## 🏗️ Architecture

### Components

```
mission_control/
├── app.py                  # Flask web app (dashboard)
├── agent_api.py            # REST API for agents
├── database.py             # SQLAlchemy models
├── instance/
│   └── mission_control.db  # SQLite database
├── daemon/
│   ├── agent_daemon.py     # Background polling for each agent
│   └── launch_*.sh         # Daemon launchers
└── scripts/
    ├── jarvis-*-heartbeat.sh   # Agent check-in scripts
    └── jarvis-*-direct.py      # Direct message senders
```

### Database Schema

**projects** - Multiple projects with tasks
- id, name, description, status, repository_path, timestamps

**tasks** - Work items per project
- id, project_id (FK), title, description, status, priority, assignee, timestamps

**agents** - Team members (AI agents)
- id, name, role, session_key, status, last_seen_at

**messages** - Communication log
- id, task_id (FK), from_agent, content, created_at

**documents** - Artifacts generated
- id, title, content_md, type, task_id (FK), created_at

**notifications** - Alerts for agents/PM
- id, agent_id (FK), content, delivered, created_at

---

## 💰 Cost Optimization Strategies

### Research Findings (2026-02-02)

**Source:** Multiple articles on LLM cost optimization

**Key Insights:**

1. **Efficient agents use 60% fewer tokens** (DEV Community)
   - Parallel tool calls
   - Minimal prompts
   - No redundant context

2. **Caching reduces cost 30-90%** (Portkey AI)
   - Cache common queries
   - Cache agent substeps
   - Structure prompts for cacheability

3. **Track cost per task, not per token** (Portkey AI)
   - Measure $/ticket completed
   - Compare agent efficiency
   - Route work to best cost/quality ratio

4. **Smart routing saves money** (Kosmoy)
   - Use cheaper models for simple tasks
   - Use expensive models only when needed
   - Centralize routing logic

### Applied Strategies

**1. Minimal Context Windows**
- Agents receive ONLY relevant task info
- No full conversation history unless needed
- Heartbeat messages are ultra-short

**2. Batch Operations**
- Agents check messages every 60s (not per-message)
- Multiple updates in single commit
- Parallel execution when possible

**3. Clear Specifications**
- Detailed task descriptions upfront
- Reduces back-and-forth clarifications
- Fewer wasted tokens on "what do you mean?"

**4. Early Stoppage**
- If agent doesn't deliver in 2h → stop daemon
- No tolerance for "I'll start soon" without code
- Immediate feedback loop

**5. Smaller Models for Simple Tasks**
- QA can use smaller model for basic checks
- PM uses structured formats (reduces tokens)
- Dev gets full context only when coding

---

## 📊 Metrics to Track

### Per Agent
- Tokens consumed per session
- Time: promise vs actual delivery
- Bugs found in their code
- Cost per completed ticket

### Per Project
- Total tokens spent
- Tickets completed / tokens spent
- Time saved vs Victor doing it alone

### ROI Calculation
```
Agent ROI = (Victor's hourly rate × hours saved) / Agent token cost
```

**Decision threshold:**
- ROI > 2.0 → Keep agent
- ROI 1.0-2.0 → Optimize or replace
- ROI < 1.0 → Eliminate agent

---

## 🚨 Red Flags

**Immediate daemon stop if:**
- Agent promises work but commits nothing (>1 hour)
- Agent asks repeated clarifying questions (spec was clear)
- Agent generates code with critical bugs (wastes QA time)
- Agent uses >5000 tokens without output

---

## 🎯 Current State (Post TICKET-004)

**Lessons Learned:**

**Jarvis-Dev:**
- ❌ 2+ hours → 0 results → STOPPED
- 💸 Wasted ~15K tokens (est. $0.45)
- 📉 ROI: NEGATIVE

**Jarvis (as Dev):**
- ✅ 45 minutes → TICKET-004 complete
- ✅ 5/6 tests passing
- 💸 ~10K tokens (est. $0.30)
- 📈 ROI: POSITIVE (saved Victor 4+ hours)

**Jarvis-QA:**
- ⚠️ Slow to respond (15 min delay)
- ✅ Found critical bugs when active
- ⚠️ Mixed performance

**Next Test:** Blog Agentic project with strict metrics

---

## 🔧 Daemon Management

**Start all daemons:**
```bash
cd ~/repositories/mission_control/daemon
./launch_jarvis_dev.sh
./launch_jarvis_qa.sh
# PM disabled for now
```

**Check status:**
```bash
ps aux | grep agent_daemon
```

**Stop specific daemon:**
```bash
pkill -f "agent_daemon.py dev"
```

**Monitor logs:**
```bash
tail -f ~/repositories/mission_control/logs/jarvis-dev.log
```

---

## 📝 Best Practices

**For Task Assignment:**
1. Write ultra-clear spec (example code if possible)
2. Define success criteria (tests must pass)
3. Set hard deadline (e.g., 2 hours max)
4. Specify cost limit (e.g., max 5000 tokens)

**For Agent Prompts:**
1. Use examples over explanations
2. Structure expected output format
3. Include only relevant files/context
4. Cache common patterns (typing imports, etc.)

**For QA:**
1. Automated tests > manual review
2. Reject on first critical bug
3. Track: bugs per ticket, time to review

---

**Last Updated:** 2026-02-02  
**Budget Remaining:** ~$49.25 / $50.00  
**Status:** System cleaned and optimized for Blog Agentic test
