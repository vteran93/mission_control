#!/usr/bin/env python3
"""
Database Logger Handler for Agent Daemons
Writes logs to SQLite for real-time dashboard display
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path


class DatabaseLogHandler(logging.Handler):
    """Custom logging handler that writes to Mission Control DB"""
    
    def __init__(self, db_path: str, agent_name: str):
        super().__init__()
        self.db_path = db_path
        self.agent_name = agent_name
        
    def emit(self, record):
        """Write log record to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert log entry
            cursor.execute("""
                INSERT INTO daemon_logs (agent_name, level, message, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                self.agent_name,
                record.levelname,
                self.format(record),
                datetime.utcnow()
            ))
            
            conn.commit()
            conn.close()
            
            # Keep only last 500 logs per agent (cleanup)
            self._cleanup_old_logs()
            
        except Exception as e:
            # Don't crash daemon if logging fails
            print(f"DB Log Error: {e}")
    
    def _cleanup_old_logs(self):
        """Keep only recent logs to prevent DB bloat"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete old logs, keep last 500 per agent
            cursor.execute("""
                DELETE FROM daemon_logs
                WHERE id NOT IN (
                    SELECT id FROM daemon_logs
                    WHERE agent_name = ?
                    ORDER BY timestamp DESC
                    LIMIT 500
                )
                AND agent_name = ?
            """, (self.agent_name, self.agent_name))
            
            conn.commit()
            conn.close()
        except:
            pass  # Cleanup is non-critical
