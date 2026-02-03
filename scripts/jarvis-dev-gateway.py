#!/usr/bin/env python3
"""
Jarvis-Dev Gateway Responder - Uses Clawdbot Gateway API (sessions_send)
"""
import sys
import os
import requests
from datetime import datetime
from pathlib import Path

# Rutas relativas a mission_control
BASE_DIR = Path(__file__).parent.parent
API_BASE = 'http://localhost:5001/api'
AGENT_NAME = 'Jarvis-Dev'
PROCESSED_FILE = BASE_DIR / 'daemon/state/dev-processed-messages.txt'

# Clawdbot Gateway API
GATEWAY_URL = 'http://localhost:3000'  # Default Clawdbot gateway port

def get_processed_messages():
    """Get IDs of already processed messages"""
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PROCESSED_FILE.exists():
        return set()
    with open(PROCESSED_FILE, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def mark_processed(msg_id):
    """Mark message as processed"""
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{msg_id}\n")

def check_messages_for_me():
    """Check recent messages mentioning me"""
    try:
        response = requests.get(f'{API_BASE}/messages')
        messages = response.json()
        
        my_messages = []
        now = datetime.now()
        
        for msg in messages:
            if msg['from_agent'] == AGENT_NAME:
                continue
            
            content_lower = msg['content'].lower()
            if 'jarvis-dev' in content_lower or '@jarvis-dev' in content_lower:
                created = datetime.fromisoformat(msg['created_at'].replace('Z', '+00:00'))
                minutes_ago = (now - created.replace(tzinfo=None)).total_seconds() / 60
                
                if minutes_ago <= 30:
                    my_messages.append(msg)
        
        return my_messages
    except Exception as e:
        print(f"⚠️ Error checking messages: {e}")
        return []

def spawn_jarvis_dev(message_content):
    """Spawn or send message to Jarvis-Dev subagent via Gateway API"""
    try:
        # Try sessions_send first (if session exists with label jarvis-dev)
        payload = {
            "tool": "sessions_send",
            "label": "jarvis-dev",
            "message": message_content,
            "timeoutSeconds": 180
        }
        
        response = requests.post(
            f'{GATEWAY_URL}/api/v1/tools',
            json=payload,
            timeout=200
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"✅ Sent to existing jarvis-dev session")
                return True
            elif 'No session found' in str(result.get('error', '')):
                # Session doesn't exist, spawn new one
                print(f"⚠️ No existing session, spawning new jarvis-dev...")
                return spawn_new_session(message_content)
        else:
            print(f"⚠️ sessions_send failed: {response.status_code}")
            return spawn_new_session(message_content)
            
    except Exception as e:
        print(f"⚠️ Error in spawn_jarvis_dev: {e}")
        return False

def spawn_new_session(message_content):
    """Spawn new Jarvis-Dev subagent"""
    try:
        payload = {
            "tool": "sessions_spawn",
            "label": "jarvis-dev",
            "task": message_content,
            "cleanup": "keep",
            "runTimeoutSeconds": 300
        }
        
        response = requests.post(
            f'{GATEWAY_URL}/api/v1/tools',
            json=payload,
            timeout=320
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"✅ Spawned new jarvis-dev session")
                return True
        
        print(f"⚠️ sessions_spawn failed: {response.status_code}")
        return False
        
    except Exception as e:
        print(f"⚠️ Error spawning session: {e}")
        return False

def main():
    processed = get_processed_messages()
    new_messages = check_messages_for_me()
    
    if not new_messages:
        print("📭 No new messages for Jarvis-Dev")
        return
    
    for msg in new_messages:
        if str(msg['id']) not in processed:
            print(f"📨 Processing message {msg['id']} from {msg['from_agent']}")
            
            # Format message for Jarvis-Dev context
            formatted_message = f"""[MISSION CONTROL MESSAGE]

From: {msg['from_agent']}
Time: {msg['created_at']}

{msg['content']}

---

**YOUR ROLE:** You are Jarvis-Dev (Python Senior Developer, 15+ years experience).

**ACTION REQUIRED:**
1. Read and understand the task/ticket
2. Execute the work (code, tests, docs)
3. Commit to git
4. Report back to Mission Control API

**Mission Control API:**
- POST http://localhost:5001/api/messages
- Body: {{"from_agent": "Jarvis-Dev", "content": "your status update"}}

**EXECUTE THE WORK NOW. DO NOT JUST ACKNOWLEDGE.**
"""
            
            if spawn_jarvis_dev(formatted_message):
                mark_processed(msg['id'])
                print(f"✅ Processed message {msg['id']}")
            else:
                print(f"⚠️ Failed to process message {msg['id']}")

if __name__ == '__main__':
    main()
