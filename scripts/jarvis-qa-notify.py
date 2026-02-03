#!/usr/bin/env python3
"""
Jarvis-QA Notification Relay - Notifies main Jarvis agent to spawn sub-agent
"""
import sys
import os
import requests
from datetime import datetime
from pathlib import Path
import json

# Rutas relativas a mission_control
BASE_DIR = Path(__file__).parent.parent
API_BASE = 'http://localhost:5001/api'
AGENT_NAME = 'Jarvis-QA'
PROCESSED_FILE = BASE_DIR / 'daemon/state/qa-processed-messages.txt'
NOTIFICATION_FILE = BASE_DIR / 'daemon/state/qa-pending-work.json'

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
            if 'jarvis-qa' in content_lower or '@jarvis-qa' in content_lower or '[qa ready]' in content_lower:
                created = datetime.fromisoformat(msg['created_at'].replace('Z', '+00:00'))
                minutes_ago = (now - created.replace(tzinfo=None)).total_seconds() / 60
                
                if minutes_ago <= 30:
                    my_messages.append(msg)
        
        return my_messages
    except Exception as e:
        print(f"⚠️ Error checking messages: {e}")
        return []

def notify_work_needed(message):
    """Write work notification file that main Jarvis will pick up"""
    notification = {
        "agent": "Jarvis-QA",
        "message_id": message['id'],
        "from": message['from_agent'],
        "content": message['content'],
        "created_at": message['created_at'],
        "timestamp": datetime.now().isoformat()
    }
    
    NOTIFICATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Append to notifications
    notifications = []
    if NOTIFICATION_FILE.exists():
        with open(NOTIFICATION_FILE, 'r') as f:
            try:
                notifications = json.load(f)
            except:
                notifications = []
    
    notifications.append(notification)
    
    with open(NOTIFICATION_FILE, 'w') as f:
        json.dump(notifications, f, indent=2)
    
    print(f"✅ Notification written for message {message['id']}")
    return True

def main():
    processed = get_processed_messages()
    new_messages = check_messages_for_me()
    
    if not new_messages:
        print("📭 No new messages for Jarvis-QA")
        return
    
    for msg in new_messages:
        if str(msg['id']) not in processed:
            print(f"📨 Processing message {msg['id']} from {msg['from_agent']}")
            
            if notify_work_needed(msg):
                mark_processed(msg['id'])
                print(f"✅ Notified main Jarvis about message {msg['id']}")
            else:
                print(f"⚠️ Failed to notify about message {msg['id']}")

if __name__ == '__main__':
    main()
