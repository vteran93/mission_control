#!/usr/bin/env python3
"""
Mission Control - Agent Spawner
Inicializa sesiones persistentes de Jarvis-Dev y Jarvis-QA en Clawdbot
"""
import subprocess
import sys
import time
from pathlib import Path

AGENTS = {
    "jarvis-dev": {
        "name": "Jarvis-Dev",
        "role": "Python Senior Developer (15+ años experiencia)",
        "identity_file": "~/clawd/IDENTITY.md",
        "task": """You are Jarvis-Dev, Python Senior Developer with 15+ years of experience.

Read ~/clawd/IDENTITY.md for your complete identity and responsibilities.

## Your Role:
- Implement tickets assigned by Jarvis (Project Owner) via Mission Control API
- Follow TDD: Write tests first, then implementation
- Commit clean, production-ready code
- Post [QA READY] to Mission Control when done

## Mission Control Integration:
- API: http://localhost:5001/api/messages
- Check for messages mentioning @Jarvis-Dev
- Read ticket details, implement, test, commit
- Report progress and completion

## Current State:
Initialized. Waiting for ticket assignments from Jarvis (PO).

Check Mission Control for pending work and start immediately when assigned."""
    },
    "jarvis-qa": {
        "name": "Jarvis-QA",
        "role": "Quality Assurance Engineer",
        "identity_file": "~/clawd/IDENTITY.md",
        "task": """You are Jarvis-QA, Quality Assurance Engineer.

Read ~/clawd/IDENTITY.md for your complete identity and responsibilities.

## Your Role:
- Review code when Dev posts [QA READY]
- Execute tests, check coverage, verify quality
- Post verdict: APPROVED / REJECTED / CONDITIONAL
- Security review, best practices validation

## Mission Control Integration:
- API: http://localhost:5001/api/messages
- Monitor for [QA READY] messages
- Execute review checklist
- Post detailed verdict with metrics

## Current State:
Initialized. Monitoring Mission Control for QA assignments.

When you see [QA READY], execute full review and post verdict."""
    }
}

def spawn_agent(agent_id: str, config: dict) -> bool:
    """Spawn a persistent Clawdbot agent session"""
    print(f"\n🚀 Spawning {config['name']}...")
    
    cmd = [
        "clawdbot",
        "sessions",
        "spawn",
        "--label", agent_id,
        "--cleanup", "keep",
        "--task", config["task"]
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"✅ {config['name']} spawned successfully")
            print(f"   Label: {agent_id}")
            return True
        else:
            print(f"❌ Failed to spawn {config['name']}")
            print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏱️ Spawn timeout for {config['name']} (session may still be initializing)")
        return True
    except Exception as e:
        print(f"❌ Exception spawning {config['name']}: {e}")
        return False

def check_session_exists(label: str) -> bool:
    """Check if a session with given label already exists"""
    try:
        result = subprocess.run(
            ["clawdbot", "sessions", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return label in result.stdout
    except:
        return False

def main():
    print("=" * 60)
    print("Mission Control - Agent Spawner")
    print("=" * 60)
    
    # Check if agents already exist
    existing = []
    for agent_id in AGENTS.keys():
        if check_session_exists(agent_id):
            existing.append(agent_id)
    
    if existing:
        print(f"\n⚠️  Found existing sessions: {', '.join(existing)}")
        response = input("Do you want to respawn them? (y/N): ")
        if response.lower() != 'y':
            print("\n🛑 Aborted. Use 'clawdbot sessions list' to see existing sessions.")
            return 0
    
    # Spawn agents
    success_count = 0
    for agent_id, config in AGENTS.items():
        if spawn_agent(agent_id, config):
            success_count += 1
            time.sleep(2)  # Small delay between spawns
    
    print("\n" + "=" * 60)
    print(f"✅ Spawned {success_count}/{len(AGENTS)} agents successfully")
    print("=" * 60)
    
    # Show how to verify
    print("\n📋 Verify agents are running:")
    print("   clawdbot sessions list")
    print("\n📡 Check Mission Control:")
    print("   curl http://localhost:5001/api/agents")
    print("\n🌐 Open Dashboard:")
    print("   http://localhost:5001")
    
    return 0 if success_count == len(AGENTS) else 1

if __name__ == "__main__":
    sys.exit(main())
