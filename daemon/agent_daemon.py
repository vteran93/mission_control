#!/usr/bin/env python3
"""
Agent Daemon - Polls Mission Control DB and triggers Clawdbot heartbeats

Architecture:
    Mission Control (SQLite) → AgentDaemon (polling) → Clawdbot heartbeat scripts

Usage:
    python3 agent_daemon.py <agent_key>
    
    agent_key: pm, dev, or qa (matches config.json)
"""

import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class AgentDaemon:
    """Daemon that polls Mission Control DB and triggers agent heartbeats"""
    
    def __init__(self, agent_key: str, config_path: str = "daemon/config.json"):
        self.agent_key = agent_key
        self.config = self._load_config(config_path)
        self.agent_config = self.config["agents"][agent_key]
        self.db_path = self.config["db_path"]
        self.polling_interval = self.config["polling_interval_seconds"]
        
        # Setup logging
        self._setup_logging()
        
        # State tracking
        self.state_file = Path(self.agent_config["state_file"])
        self.state = self._load_state()
        
        self.logger.info(f"🤖 {self.agent_config['name']} Daemon initialized")
        self.logger.info(f"📋 Polling interval: {self.polling_interval}s")
        self.logger.info(f"💾 DB: {self.db_path}")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load daemon configuration"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def _setup_logging(self):
        """Configure logging"""
        log_file = Path(self.agent_config["log_file"])
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup standard file + console logging
        logging.basicConfig(
            level=getattr(logging, self.config["log_level"]),
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(f"AgentDaemon.{self.agent_key}")
        
        # Add database logging for real-time dashboard
        try:
            from db_logger import DatabaseLogHandler
            db_handler = DatabaseLogHandler(self.db_path, self.agent_key)
            db_handler.setLevel(logging.INFO)  # Only INFO+ to DB
            db_handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(db_handler)
        except Exception as e:
            self.logger.warning(f"Could not setup DB logging: {e}")
    
    def _load_state(self) -> Dict:
        """Load persistent state (last processed message ID)"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.logger.info(f"📂 State loaded: last_message_id={state.get('last_message_id', 0)}")
                return state
        
        return {"last_message_id": 0}
    
    def _save_state(self):
        """Save persistent state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _get_new_messages(self) -> list:
        """Query DB for new messages mentioning this agent"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find messages with agent mention that are newer than last processed
            agent_name_lower = self.agent_config['name'].lower()
            mention_pattern = f"%@{agent_name_lower}%"
            
            query = """
                SELECT id, from_agent, content, created_at
                FROM messages
                WHERE id > ? 
                  AND LOWER(content) LIKE ?
                ORDER BY id ASC
            """
            
            cursor.execute(query, (self.state["last_message_id"], mention_pattern))
            messages = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return messages
            
        except sqlite3.Error as e:
            self.logger.error(f"❌ DB error: {e}")
            return []
    
    def _trigger_heartbeat(self, message: Dict) -> bool:
        """Execute heartbeat script for this agent"""
        script_path = self.agent_config["heartbeat_script"]
        
        if not os.path.exists(script_path):
            self.logger.error(f"❌ Heartbeat script not found: {script_path}")
            return False
        
        try:
            self.logger.info(f"🔔 Triggering heartbeat: {script_path}")
            self.logger.info(f"   Message ID: {message['id']} from {message['from_agent']}")
            
            result = subprocess.run(
                ["/bin/bash", script_path],
                capture_output=True,
                text=True,
                timeout=self.config["heartbeat_timeout_seconds"]
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ Heartbeat completed successfully")
                return True
            else:
                self.logger.warning(f"⚠️ Heartbeat exited with code {result.returncode}")
                self.logger.warning(f"   stderr: {result.stderr[:200]}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"⏱️ Heartbeat timeout ({self.config['heartbeat_timeout_seconds']}s)")
            return False
        except Exception as e:
            self.logger.error(f"❌ Heartbeat error: {e}")
            return False
    
    def poll_and_process(self):
        """Single polling cycle: check for new messages and process them"""
        messages = self._get_new_messages()
        
        if not messages:
            self.logger.debug(f"🔍 No new messages (last_id: {self.state['last_message_id']})")
            return
        
        self.logger.info(f"📬 Found {len(messages)} new message(s)")
        
        for message in messages:
            self.logger.info(f"📨 Processing message {message['id']}: {message['content'][:60]}...")
            
            # Trigger heartbeat
            success = self._trigger_heartbeat(message)
            
            # Update state (even if trigger failed, don't re-process same message)
            self.state["last_message_id"] = message["id"]
            self._save_state()
            
            if success:
                self.logger.info(f"✅ Message {message['id']} processed successfully")
            else:
                self.logger.warning(f"⚠️ Message {message['id']} processed with errors")
    
    def run(self):
        """Main daemon loop"""
        self.logger.info(f"🚀 Starting daemon loop for {self.agent_config['name']}")
        self.logger.info(f"⏰ Polling every {self.polling_interval} seconds")
        self.logger.info(f"🛑 Press Ctrl+C to stop")
        
        try:
            while True:
                self.poll_and_process()
                time.sleep(self.polling_interval)
                
        except KeyboardInterrupt:
            self.logger.info(f"🛑 Daemon stopped by user")
        except Exception as e:
            self.logger.error(f"💥 Unexpected error: {e}")
            raise


def main():
    """Entry point"""
    if len(sys.argv) != 2:
        print("Usage: python3 agent_daemon.py <agent_key>")
        print("  agent_key: pm, dev, or qa")
        sys.exit(1)
    
    agent_key = sys.argv[1]
    
    if agent_key not in ["pm", "dev", "qa"]:
        print(f"❌ Invalid agent_key: {agent_key}")
        print("   Valid options: pm, dev, qa")
        sys.exit(1)
    
    daemon = AgentDaemon(agent_key)
    daemon.run()


if __name__ == "__main__":
    main()
