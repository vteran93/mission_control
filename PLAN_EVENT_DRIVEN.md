# Event-Driven Agent Spawning - Implementation Plan

## ✅ Phase 1: COMPLETED (80%)

### Implemented:
1. ✅ **DB Schema** - `task_queue` table created (migration 002)
2. ✅ **Model** - `TaskQueue` SQLAlchemy model with relationships
3. ✅ **Daemon Update** - `agent_daemon.py` now calls `_queue_task()` instead of JSON writes
4. ✅ **Spawner Service** - `daemon/spawner.py` polls queue and executes `clawdbot spawn`
5. ✅ **API Endpoints** - `/api/queue` and `/api/queue/<id>` working
6. ✅ **Priority System** - URGENT, HIGH, NORMAL, LOW based on message content
7. ✅ **Retry Logic** - Failed tasks retry up to 3 times

### Testing Status:
- ✅ DB queue writes correctly
- ✅ API returns queue status
- 🚧 **Spawner needs live test** (clawdbot spawn subprocess)
- 🚧 Full flow test: message → queue → spawn → agent reports back

---

## 🚧 Phase 2: PENDING (Completion Tasks)

### 2.1 Test Spawner Service (30 min)

**Actions:**
1. Wait for daemon to detect message #88 (next 60s poll)
2. Verify task queued in DB: `SELECT * FROM task_queue WHERE message_id = 88`
3. Monitor spawner logs for spawn attempt
4. Verify `clawdbot spawn` subprocess executes correctly
5. Check session_key saved to `task_queue.clawdbot_session_key`

**Expected behavior:**
```
[Daemon] Message 88 detected → Task queued (status='pending')
[Spawner] Task detected → Mark processing → Execute clawdbot spawn
[Spawner] Session key returned → Mark completed
```

**Potential issues:**
- clawdbot CLI not in PATH for subprocess
- Spawn output parsing (need to extract session_key)
- Timeout issues (30s limit may be too short)

**Fix if needed:**
- Increase spawn timeout to 60s
- Better session_key extraction from stdout
- Add more verbose logging in spawner.py

---

### 2.2 Remove Deprecated JSON System (20 min)

**Files to clean:**
- Delete `daemon/state/*-pending-work.json`
- Delete `daemon/state/*-processed-messages.txt`
- Remove `scripts/jarvis-dev-notify.py`
- Remove `scripts/jarvis-qa-notify.py`
- Remove `scripts/jarvis-*-heartbeat.sh` (no longer needed)

**Update:**
- `daemon/config.json` - Remove `heartbeat_script` references
- `~/clawd/HEARTBEAT.md` - Remove daemon notification block
- `~/clawd/process_daemon_notifications.py` - Deprecate or remove

---

### 2.3 Dashboard Queue Monitor (45 min)

**Frontend changes needed:**

**templates/index.html:**
```html
<section class="panel">
    <h2>⚙️ Agent Spawn Queue</h2>
    <div class="queue-summary">
        <div class="stat pending">📝 Pending: <span id="queue-pending">0</span></div>
        <div class="stat processing">🔨 Processing: <span id="queue-processing">0</span></div>
        <div class="stat completed">✅ Completed: <span id="queue-completed">0</span></div>
        <div class="stat failed">❌ Failed: <span id="queue-failed">0</span></div>
    </div>
    
    <h3>Pending Tasks</h3>
    <div id="pending-tasks-list" class="tasks-list">
        <!-- Populated by JS -->
    </div>
    
    <h3>Recent Tasks (Last 10)</h3>
    <div id="recent-tasks-list" class="tasks-list">
        <!-- Populated by JS -->
    </div>
</section>
```

**static/script.js:**
```javascript
async function refreshQueue() {
    const response = await fetch('/api/queue');
    const data = await response.json();
    
    // Update summary
    document.getElementById('queue-pending').textContent = data.summary.pending;
    document.getElementById('queue-processing').textContent = data.summary.processing;
    document.getElementById('queue-completed').textContent = data.summary.completed;
    document.getElementById('queue-failed').textContent = data.summary.failed;
    
    // Render pending tasks
    renderPendingTasks(data.pending_tasks);
    
    // Render recent tasks
    renderRecentTasks(data.recent_tasks.slice(0, 10));
}

// Auto-refresh every 3 seconds
setInterval(refreshQueue, 3000);
```

**static/style.css:**
```css
.queue-summary {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 15px;
    margin-bottom: 20px;
}

.stat {
    padding: 15px;
    border-radius: 6px;
    text-align: center;
    font-weight: 600;
}

.stat.pending { background: rgba(88, 166, 255, 0.1); border: 1px solid #58a6ff; }
.stat.processing { background: rgba(210, 153, 34, 0.1); border: 1px solid #d29922; }
.stat.completed { background: rgba(46, 160, 67, 0.1); border: 1px solid #2ea043; }
.stat.failed { background: rgba(248, 81, 73, 0.1); border: 1px solid #f85149; }
```

---

### 2.4 Spawner as Systemd Service (Optional - Production)

**File:** `/etc/systemd/system/mission-control-spawner.service`
```ini
[Unit]
Description=Mission Control Agent Spawner
After=network.target

[Service]
Type=simple
User=victor
WorkingDirectory=/home/victor/repositories/mission_control
ExecStart=/usr/bin/python3 /home/victor/repositories/mission_control/daemon/spawner.py
Restart=always
RestartSec=10
StandardOutput=append:/home/victor/repositories/mission_control/logs/spawner.log
StandardError=append:/home/victor/repositories/mission_control/logs/spawner-error.log

[Install]
WantedBy=multi-user.target
```

**Commands:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable mission-control-spawner
sudo systemctl start mission-control-spawner
sudo systemctl status mission-control-spawner
```

---

## 🎯 Success Criteria

- [ ] Message posted to Mission Control → Task queued within 60s
- [ ] Spawner detects task → Spawns agent within 10s
- [ ] Agent session created successfully
- [ ] Agent reports back to Mission Control
- [ ] Task marked 'completed' with session_key
- [ ] Dashboard shows queue status in real-time
- [ ] No JSON files used (fully DB-driven)
- [ ] System runs autonomously (no manual Jarvis heartbeat needed)

---

## 📊 Performance Comparison

### Before (JSON + Heartbeat):
- **Latency:** 0-15 minutes (heartbeat dependent)
- **Reliability:** Medium (depends on Jarvis availability)
- **Observability:** Low (logs in files)
- **Scalability:** Poor (single heartbeat thread)

### After (DB Queue + Spawner):
- **Latency:** 5-65 seconds (daemon poll 60s + spawner poll 5s)
- **Reliability:** High (independent service)
- **Observability:** High (DB queryable, dashboard visible)
- **Scalability:** Good (can run multiple spawners)

---

## 🚀 Next Session Action Items

1. **Test spawner with live message** (wait for daemon poll)
2. **Fix any spawn subprocess issues**
3. **Remove JSON notification system**
4. **Add queue monitor to dashboard**
5. **Document new architecture in WORKFLOW.md**

---

**Current Status:** 80% complete, core architecture working, needs live testing + cleanup
