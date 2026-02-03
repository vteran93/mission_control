#!/bin/bash
# Jarvis-QA Direct Heartbeat

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$BASE_DIR/logs/heartbeats/qa-heartbeat.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$(dirname "$LOG_FILE")"

echo "[$TIMESTAMP] Jarvis-QA direct heartbeat..." >> "$LOG_FILE"

python3 "$SCRIPT_DIR/jarvis-qa-notify.py" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo "[$TIMESTAMP] ✅ Direct heartbeat OK" >> "$LOG_FILE"
else
  echo "[$TIMESTAMP] ❌ Direct heartbeat failed: $EXIT_CODE" >> "$LOG_FILE"
fi
