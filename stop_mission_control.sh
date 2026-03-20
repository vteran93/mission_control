#!/bin/bash
# Mission Control Stop Script
# Ubicación: ~/repositories/mission_control/stop_mission_control.sh

PID_FILE="$HOME/repositories/mission_control/mission_control.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No se encontró PID file. Buscando procesos manualmente..."
    pkill -f "python3.*app.py" && echo "✅ Procesos terminados" || echo "❌ No se encontraron procesos"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "🛑 Deteniendo Mission Control (PID: $PID)..."
    kill "$PID"
    sleep 2
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  Proceso no respondió a SIGTERM, forzando..."
        kill -9 "$PID"
    fi
    
    rm "$PID_FILE"
    echo "✅ Mission Control detenido"
else
    echo "⚠️  PID $PID no está corriendo"
    rm "$PID_FILE"
fi
