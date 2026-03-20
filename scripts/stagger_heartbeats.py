#!/usr/bin/env python3
"""
Staggered Heartbeat Generator
Generates clawdbot cron commands with staggered schedules to prevent simultaneous agent wakes
"""

AGENTS = {
    'Jarvis': {
        'schedule': '0,15,30,45 * * * *',  # Squad lead - highest frequency
        'session_key': 'agent:main:main',
        'priority': 'HIGH'
    },
    'Jarvis-Dev': {
        'schedule': '2,17,32,47 * * * *',
        'session_key': 'agent:dev:main',
        'priority': 'HIGH'
    },
    'Jarvis-PM': {
        'schedule': '4,19,34,49 * * * *',
        'session_key': 'agent:pm:main',
        'priority': 'MEDIUM'
    },
    'Jarvis-QA': {
        'schedule': '6,21,36,51 * * * *',
        'session_key': 'agent:qa:main',
        'priority': 'MEDIUM'
    }
}

HEARTBEAT_MESSAGE = "Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."

def generate_cron_commands():
    """Generate clawdbot cron add commands for all agents"""
    commands = []
    
    for agent, config in AGENTS.items():
        cmd = f"""clawdbot cron add \\
  --name '{agent.lower()}-heartbeat' \\
  --cron '{config['schedule']}' \\
  --session 'isolated' \\
  --context-messages 0 \\
  --message '{HEARTBEAT_MESSAGE}'"""
        commands.append(cmd)
    
    return commands

if __name__ == '__main__':
    print("# Staggered Heartbeat Cron Commands")
    print("# Generated:", __file__)
    print()
    
    commands = generate_cron_commands()
    
    for i, cmd in enumerate(commands, 1):
        print(f"# Agent {i}")
        print(cmd)
        print()
