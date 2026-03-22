#!/bin/bash
# Mission Control Startup Script
# Ubicación: ~/repositories/mission_control/start_mission_control.sh

set -e

REPO_DIR="$HOME/repositories/mission_control"
LOG_DIR="$REPO_DIR/logs"
PID_FILE="$REPO_DIR/mission_control.pid"
PORT="${PORT:-5001}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"

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
if [ ! -x "$PYTHON_BIN" ]; then
    echo "❌ No se encontró Python virtualenv en $PYTHON_BIN"
    echo "Crea la venv o exporta PYTHON_BIN antes de ejecutar."
    exit 1
fi

if ! "$PYTHON_BIN" -m pip list | grep -q Flask; then
    echo "📦 Instalando dependencias..."
    "$PYTHON_BIN" -m pip install -r requirements-dev.txt
fi

# Iniciar servidor en background
echo "🚀 Iniciando Mission Control..."
nohup env PORT="$PORT" "$PYTHON_BIN" app.py > "$LOG_DIR/mission_control.log" 2>&1 &
PID=$!

# Guardar PID
echo "$PID" > "$PID_FILE"

# Esperar 2 segundos para verificar startup
sleep 2

# Verificar que levantó correctamente
if ps -p "$PID" > /dev/null; then
    if curl -s "http://localhost:${PORT}/api/health" > /dev/null 2>&1; then
        echo "✅ Mission Control ONLINE (PID: $PID)"
        echo "📊 Dashboard: http://localhost:${PORT}"
        echo "🔧 API: http://localhost:${PORT}/api/tasks"
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
