#!/bin/bash
# Mission Control Status Check
# Ubicación: ~/repositories/mission_control/status_mission_control.sh

PID_FILE="$HOME/repositories/mission_control/mission_control.pid"
LOG_DIR="$HOME/repositories/mission_control/logs"

echo "🔍 Mission Control Status Check"
echo "================================"

# Verificar PID file
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ Proceso: RUNNING (PID: $PID)"
    else
        echo "⚠️  Proceso: STOPPED (PID file stale)"
    fi
else
    echo "❌ Proceso: NO PID FILE"
fi

# Verificar puerto
if netstat -tuln 2>/dev/null | grep -q ":5001 "; then
    echo "✅ Puerto 5001: LISTENING"
else
    echo "❌ Puerto 5001: NOT LISTENING"
fi

# Verificar API
if curl -s -f http://localhost:5001/api/tasks > /dev/null 2>&1; then
    TASK_COUNT=$(curl -s http://localhost:5001/api/tasks | jq '. | length' 2>/dev/null || echo "?")
    echo "✅ API: RESPONDING ($TASK_COUNT tasks)"
else
    echo "❌ API: NOT RESPONDING"
fi

# Últimos logs
echo ""
echo "📋 Últimos 5 logs:"
if [ -f "$LOG_DIR/mission_control.log" ]; then
    tail -5 "$LOG_DIR/mission_control.log" | sed 's/^/   /'
else
    echo "   (no log file found)"
fi

echo ""
echo "🔗 Dashboard: http://localhost:5001"
