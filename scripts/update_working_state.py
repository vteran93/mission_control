#!/usr/bin/env python3
"""
WORKING.md State Updater
Auto-updates WORKING.md with current Mission Control state
Run during every heartbeat for accurate state tracking
"""

import sqlite3
import re
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / 'repositories/mission_control/instance/mission_control.db'
WORKING_PATH = Path.home() / 'clawd/memory/WORKING.md'

def update_working_md():
    """Update WORKING.md with current database state"""
    
    if not DB_PATH.exists():
        print(f"⚠️  Database not found: {DB_PATH}")
        return False
    
    if not WORKING_PATH.exists():
        print(f"⚠️  WORKING.md not found: {WORKING_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        
        # Query current state
        pending = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='todo'").fetchone()[0]
        in_progress = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='in_progress'").fetchone()[0]
        in_review = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='review'").fetchone()[0]
        blocked = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='blocked'").fetchone()[0]
        
        # Get recent message count (last hour)
        msg_count = conn.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE created_at >= datetime('now', '-1 hour')
        """).fetchone()[0]
        
        conn.close()
        
        # Read current WORKING.md
        with open(WORKING_PATH, 'r') as f:
            content = f.read()
        
        # Update stats section
        content = re.sub(
            r'\*\*Pending Tasks:\*\* \d+',
            f'**Pending Tasks:** {pending}',
            content
        )
        
        content = re.sub(
            r'\*\*Tasks in Review:\*\* \d+',
            f'**Tasks in Review:** {in_review}',
            content
        )
        
        content = re.sub(
            r'\*\*Messages Last Hour:\*\* \d+',
            f'**Messages Last Hour:** {msg_count}',
            content
        )
        
        # Update timestamp
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = re.sub(
            r'\*\*Last Updated:\*\* .*',
            f'**Last Updated:** {now_str}',
            content
        )
        
        # Write updated content
        with open(WORKING_PATH, 'w') as f:
            f.write(content)
        
        print(f"✅ WORKING.md updated: {pending} pending, {in_progress} active, {in_review} review, {blocked} blocked")
        return True
        
    except Exception as e:
        print(f"❌ Error updating WORKING.md: {e}")
        return False

if __name__ == '__main__':
    import sys
    success = update_working_md()
    sys.exit(0 if success else 1)
