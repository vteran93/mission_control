#!/usr/bin/env python3
"""
Migration script to add daemon_logs table to Mission Control DB
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'instance' / 'mission_control.db'

def migrate():
    """Add daemon_logs table if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='daemon_logs'
    """)
    
    if cursor.fetchone():
        print("✅ daemon_logs table already exists")
    else:
        print("📝 Creating daemon_logs table...")
        cursor.execute("""
            CREATE TABLE daemon_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name VARCHAR(50) NOT NULL,
                level VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME NOT NULL
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX idx_daemon_logs_agent ON daemon_logs(agent_name)")
        cursor.execute("CREATE INDEX idx_daemon_logs_timestamp ON daemon_logs(timestamp)")
        
        conn.commit()
        print("✅ daemon_logs table created with indexes")
    
    conn.close()

if __name__ == '__main__':
    migrate()
    print("🎉 Migration complete")
