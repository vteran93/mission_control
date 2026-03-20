#!/bin/bash
# Mission Control Startup Script
# Ubicación: ~/repositories/mission_control/start_mission_control.sh

set -e

REPO_DIR="$HOME/repositories/mission_control"
LOG_DIR="$REPO_DIR/logs"
PID_FILE="$REPO_DIR/mission_control.pid"

# Crear directorio de logs si no existe
mkdir -p "$LOG_DIR"

# Verificar si ya está corriendo
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  Mission Control ya está corriendo (PID: $OLD_PID)"
        echo "Para reiniciar: kill $OLD_PID && $0"
        exit 1
    else
        rm "$PID_FILE"
    fi
fi

# Navegar al directorio
cd "$REPO_DIR"

# Verificar dependencias
if ! pip3 list | grep -q Flask; then
    echo "📦 Instalando dependencias..."
    pip3 install -r requirements.txt
fi

# Iniciar servidor en background
echo "🚀 Iniciando Mission Control..."
nohup python3 app.py > "$LOG_DIR/mission_control.log" 2>&1 &
PID=$!

# Guardar PID
echo "$PID" > "$PID_FILE"

# Esperar 2 segundos para verificar startup
sleep 2

# Verificar que levantó correctamente
if ps -p "$PID" > /dev/null; then
    if curl -s http://localhost:5001/api/tasks > /dev/null 2>&1; then
        echo "✅ Mission Control ONLINE (PID: $PID)"
        echo "📊 Dashboard: http://localhost:5001"
        echo "🔧 API: http://localhost:5001/api/tasks"
        echo "📋 Logs: tail -f $LOG_DIR/mission_control.log"
    else
        echo "⚠️  Proceso corriendo pero API no responde"
        echo "📋 Revisar logs: tail -f $LOG_DIR/mission_control.log"
    fi
else
    echo "❌ ERROR: Proceso no pudo iniciar"
    rm "$PID_FILE"
    tail -20 "$LOG_DIR/mission_control.log"
    exit 1
fi
