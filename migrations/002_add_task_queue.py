#!/usr/bin/env python3
"""
Migration 002: Add task_queue table for event-driven agent spawning
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'instance' / 'mission_control.db'

def upgrade():
    """Create task_queue table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("📝 Creating task_queue table...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_agent VARCHAR(50) NOT NULL,
            message_id INTEGER NOT NULL,
            from_agent VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            priority VARCHAR(20) DEFAULT 'normal',
            status VARCHAR(20) DEFAULT 'pending',
            
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            
            clawdbot_session_key TEXT,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            
            FOREIGN KEY (message_id) REFERENCES messages(id)
        )
    """)
    
    print("📊 Creating indexes...")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON task_queue(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_target ON task_queue(target_agent)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_priority ON task_queue(priority, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_message ON task_queue(message_id)")
    
    conn.commit()
    conn.close()
    
    print("✅ task_queue table created successfully")

def downgrade():
    """Drop task_queue table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS task_queue")
    
    conn.commit()
    conn.close()
    
    print("✅ task_queue table dropped")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        downgrade()
    else:
        upgrade()
