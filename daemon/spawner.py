#!/usr/bin/env python3
"""
Mission Control Agent Spawner Service - v2 (HTTP API)

Polls task_queue DB and spawns agents via Clawdbot Gateway HTTP API (/tools/invoke)
"""
import json
import os
import sqlite3
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

# Configuration
DB_PATH = Path(__file__).parent.parent / 'instance' / 'mission_control.db'
POLL_INTERVAL = 5  # seconds
MAX_RETRIES = 3
GATEWAY_URL = 'http://127.0.0.1:18789'
# Token from environment variable (auto-extracted from config in .zshrc)
GATEWAY_TOKEN = os.getenv('CLAWDBOT_GATEWAY_TOKEN', '')

def log(message):
    """Simple logging with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}", flush=True)

def get_pending_tasks(conn):
    """Get all pending tasks ordered by priority"""
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
    """, (MAX_RETRIES,))
    
    return [dict(row) for row in cursor.fetchall()]

def spawn_agent_via_api(task):
    """Spawn agent using Clawdbot Gateway HTTP API"""
    agent_label = task['target_agent']
    
    payload = {
        'tool': 'sessions_spawn',
        'args': {
            'label': agent_label,
            'task': f"""[MISSION CONTROL WORK]

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

**IMPORTANT:** Post completion status to Mission Control.""",
            'cleanup': 'keep',
            'runTimeoutSeconds': 7200
        }
    }
    
    try:
        response = requests.post(
            f'{GATEWAY_URL}/tools/invoke',
            headers={
                'Authorization': f'Bearer {GATEWAY_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                # childSessionKey is in result.details
                details = result.get('result', {}).get('details', {})
                session_key = details.get('childSessionKey', 'unknown')
                return {'success': True, 'session_key': session_key}
            else:
                return {'success': False, 'error': result.get('error', {}).get('message', 'Unknown error')}
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
            
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'Request failed: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

def process_task(task, conn):
    """Process a single task"""
    task_id = task['id']
    agent_label = task['target_agent']
    
    log(f"🔨 Processing task #{task_id}: {agent_label}")
    log(f"   📨 Message #{task['message_id']} from {task['from_agent']}")
    log(f"   ⚡ Priority: {task['priority']}")
    
    # Mark as processing
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE task_queue
        SET status = 'processing', started_at = datetime('now')
        WHERE id = ?
    """, (task_id,))
    conn.commit()
    
    # Spawn via HTTP API
    log(f"   🚀 Spawning via Gateway HTTP API...")
    result = spawn_agent_via_api(task)
    
    if result['success']:
        # Mark as completed
        cursor.execute("""
            UPDATE task_queue
            SET status = 'completed',
                completed_at = datetime('now'),
                clawdbot_session_key = ?
            WHERE id = ?
        """, (result['session_key'], task_id))
        conn.commit()
        
        log(f"   ✅ Task #{task_id} completed successfully")
        log(f"   🔑 Session: {result['session_key']}")
        return True
    else:
        # Mark as failed or retry
        retry_count = task['retry_count'] + 1
        if retry_count < MAX_RETRIES:
            cursor.execute("""
                UPDATE task_queue
                SET status = 'pending',
                    retry_count = ?,
                    error_message = ?
                WHERE id = ?
            """, (retry_count, result['error'][:500], task_id))
            conn.commit()
            log(f"   ⚠️  Spawn failed: {result['error']}")
            log(f"   ⏳ Will retry (attempt {retry_count + 1}/{MAX_RETRIES})")
        else:
            cursor.execute("""
                UPDATE task_queue
                SET status = 'failed',
                    retry_count = ?,
                    error_message = ?
                WHERE id = ?
            """, (retry_count, result['error'][:500], task_id))
            conn.commit()
            log(f"   ❌ Task #{task_id} failed permanently after {MAX_RETRIES} attempts")
            log(f"   💥 Error: {result['error']}")
        
        return False

def main():
    """Main spawner loop"""
    if not GATEWAY_TOKEN:
        log("❌ ERROR: CLAWDBOT_GATEWAY_TOKEN not set")
        sys.exit(1)
    
    log("🚀 Mission Control Agent Spawner Service (HTTP API)")
    log(f"📊 Database: {DB_PATH}")
    log(f"🌐 Gateway: {GATEWAY_URL}")
    log(f"⏰ Poll interval: {POLL_INTERVAL}s")
    log(f"🔁 Max retries: {MAX_RETRIES}")
    log(f"🛑 Press Ctrl+C to stop")
    log("")
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    try:
        while True:
            tasks = get_pending_tasks(conn)
            
            if tasks:
                log(f"📋 Found {len(tasks)} pending task(s)")
                for task in tasks:
                    process_task(task, conn)
                    log("")
            
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        log("\n👋 Shutting down...")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
