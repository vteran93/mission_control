#!/usr/bin/env python3
"""
Jarvis-QA Direct Responder - Responde directamente via clawdbot agent
"""
import sys
import os
import requests
import subprocess
from datetime import datetime
from pathlib import Path

# Rutas relativas a mission_control
BASE_DIR = Path(__file__).parent.parent
API_BASE = 'http://localhost:5001/api'
AGENT_NAME = 'Jarvis-QA'
PROCESSED_FILE = BASE_DIR / 'daemon/state/qa-processed-messages.txt'

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
            if 'jarvis-qa' in content_lower or '@jarvis-qa' in content_lower:
                created = datetime.fromisoformat(msg['created_at'].replace('Z', '+00:00'))
                minutes_ago = (now - created.replace(tzinfo=None)).total_seconds() / 60
                
                if minutes_ago <= 30:
                    my_messages.append(msg)
        
        return my_messages
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return []

def respond_via_clawdbot(message_content):
    """Respond using clawdbot agent command"""
    prompt = f"""Lee tu IDENTITY.md. Mensaje recibido:

"{message_content}"

Responde profesionalmente Y ejecuta:

import requests
requests.post('http://localhost:5001/api/messages', json={{'from_agent': 'Jarvis-QA', 'content': 'TU_RESPUESTA'}})"""
    
    try:
        result = subprocess.run(
            ['clawdbot', 'agent', '--agent', 'jarvis-qa', '--message', prompt, '--local'],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return False

def main():
    processed = get_processed_messages()
    new_messages = check_messages_for_me()
    
    for msg in new_messages:
        if str(msg['id']) not in processed:
            print(f"📨 Processing message {msg['id']} from {msg['from_agent']}")
            if respond_via_clawdbot(msg['content']):
                mark_processed(msg['id'])
                print(f"✅ Responded to {msg['id']}")
            else:
                print(f"⚠️ Failed to respond to {msg['id']}")

if __name__ == '__main__':
    main()
