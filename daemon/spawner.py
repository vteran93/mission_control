#!/usr/bin/env python3
"""
Agent Spawner Service - Event-driven agent spawning from task queue
Reemplaza el flujo manual de JSON → Jarvis heartbeat → spawn
"""
import sys
import sqlite3
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'instance' / 'mission_control.db'
POLL_INTERVAL = 5  # segundos
MAX_RETRIES = 3

def log(message):
    """Simple logging with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}", flush=True)

def get_pending_tasks():
    """Get pending tasks ordered by priority"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM task_queue
        WHERE status = 'pending' AND retry_count < ?
        ORDER BY 
            CASE priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            created_at ASC
        LIMIT 5
    """, (MAX_RETRIES,))
    
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def mark_task_processing(task_id):
    """Mark task as processing"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE task_queue 
        SET status = 'processing', started_at = ?
        WHERE id = ?
    """, (datetime.now(), task_id))
    conn.commit()
    conn.close()

def mark_task_completed(task_id, session_key):
    """Mark task as completed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE task_queue 
        SET status = 'completed', 
            completed_at = ?,
            clawdbot_session_key = ?
        WHERE id = ?
    """, (datetime.now(), session_key, task_id))
    conn.commit()
    conn.close()

def mark_task_failed(task_id, error):
    """Mark task as failed (increment retry)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE task_queue 
        SET status = 'failed', 
            error_message = ?,
            retry_count = retry_count + 1
        WHERE id = ?
    """, (error[:500], task_id))
    conn.commit()
    
    # Check retry count
    cursor.execute("SELECT retry_count FROM task_queue WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    retry_count = row[0] if row else 0
    
    conn.close()
    
    if retry_count < MAX_RETRIES:
        # Reset to pending for retry
        reset_to_pending(task_id)
        log(f"   ⚠️  Will retry (attempt {retry_count + 1}/{MAX_RETRIES})")
    else:
        log(f"   ❌ Max retries reached, giving up")

def reset_to_pending(task_id):
    """Reset failed task to pending for retry"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE task_queue 
        SET status = 'pending'
        WHERE id = ?
    """, (task_id,))
    conn.commit()
    conn.close()

def spawn_agent(task):
    """Spawn agent via clawdbot CLI subprocess"""
    agent_label = task['target_agent']
    
    # Build task content
    task_content = f"""[MISSION CONTROL WORK]

Message ID: {task['message_id']}
From: {task['from_agent']}

{task['content']}

---

**YOUR IDENTITY:** {agent_label.title().replace('-', ' ')}

**ACTION:** Execute the work described above. DO NOT just acknowledge.

**WORKFLOW:**
1. Understand the ticket/task
2. Write code + tests (if Dev) or execute review (if QA) or report status (if PM)
3. Commit to git (if code changes)
4. Report back to Mission Control API (POST http://localhost:5001/api/messages)

**IMPORTANT:** Post completion status to Mission Control.
"""
    
    # Execute clawdbot spawn via subprocess
    try:
        log(f"   🚀 Executing: clawdbot spawn --label {agent_label}")
        
        result = subprocess.run(
            [
                'clawdbot', 'spawn',
                '--label', agent_label,
                '--cleanup', 'keep',
                '--timeout', '7200',
                '--task', task_content
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Parse output for session key
            output = result.stdout.strip()
            
            # Try to extract session key from output
            session_key = None
            for line in output.split('\n'):
                if 'sessionKey' in line or 'session' in line.lower():
                    # Attempt basic extraction
                    if ':' in line:
                        session_key = line.split(':', 1)[1].strip()
                        break
            
            if not session_key:
                session_key = f"spawned-{task['id']}-{int(time.time())}"
            
            log(f"   ✅ Spawned successfully")
            log(f"   📝 Session: {session_key[:50]}...")
            
            return session_key
        else:
            error = result.stderr or result.stdout or "Unknown error"
            log(f"   ❌ Spawn failed: {error[:200]}")
            return None
            
    except subprocess.TimeoutExpired:
        log(f"   ⏱️  Spawn timeout (30s)")
        return None
    except FileNotFoundError:
        log(f"   ❌ clawdbot CLI not found in PATH")
        return None
    except Exception as e:
        log(f"   ⚠️  Exception: {str(e)[:200]}")
        return None

def main():
    """Main spawner loop"""
    log("🚀 Mission Control Agent Spawner Service")
    log(f"📊 Database: {DB_PATH}")
    log(f"⏰ Poll interval: {POLL_INTERVAL}s")
    log(f"🔁 Max retries: {MAX_RETRIES}")
    log("🛑 Press Ctrl+C to stop\n")
    
    while True:
        try:
            tasks = get_pending_tasks()
            
            if tasks:
                log(f"📋 Found {len(tasks)} pending task(s)")
                
                for task in tasks:
                    log(f"\n🔨 Processing task #{task['id']}: {task['target_agent']}")
                    log(f"   📨 Message #{task['message_id']} from {task['from_agent']}")
                    log(f"   ⚡ Priority: {task['priority']}")
                    
                    mark_task_processing(task['id'])
                    
                    session_key = spawn_agent(task)
                    
                    if session_key:
                        mark_task_completed(task['id'], session_key)
                        log(f"   ✅ Task #{task['id']} completed")
                    else:
                        mark_task_failed(task['id'], "Spawn subprocess failed")
                        log(f"   ❌ Task #{task['id']} failed")
                
                log("")  # Blank line
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            log("\n\n👋 Shutting down spawner service...")
            break
        except Exception as e:
            log(f"⚠️  Error in spawner loop: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()
