#!/bin/bash
# Launch script for Jarvis-PM daemon

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🤖 Starting Jarvis-PM Daemon..."
python3 daemon/agent_daemon.py pm
