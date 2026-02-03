#!/usr/bin/env python3
"""
Process Task Queue - Read pending tasks from DB queue for Jarvis to spawn

This script is called from Jarvis heartbeat (HEARTBEAT.md) to detect work
that needs agent spawning.

Output: JSON array of pending tasks, or "NO_TASKS"
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path.home() / 'repositories' / 'mission_control' / 'instance' / 'mission_control.db'

def get_pending_tasks():
    """Get all pending tasks from queue"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM task_queue
            WHERE status = 'pending'
            ORDER BY 
                CASE priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'normal' THEN 3
                    WHEN 'low' THEN 4
                END,
                created_at ASC
        """)
        
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not tasks:
            return None
        
        return tasks
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return None

def main():
    tasks = get_pending_tasks()
    
    if not tasks:
        print("NO_TASKS")
    else:
        print(json.dumps(tasks, indent=2))

if __name__ == '__main__':
    import sys
    main()
