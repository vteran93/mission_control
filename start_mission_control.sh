#!/bin/bash
# Mission Control Startup Script

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$REPO_DIR/logs"
PID_FILE="$REPO_DIR/mission_control.pid"
PORT="${PORT:-5001}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
TARGET_PYTHON_VERSION="${TARGET_PYTHON_VERSION:-3.12}"
AUTO_BOOTSTRAP_LOCAL_ENV="${AUTO_BOOTSTRAP_LOCAL_ENV:-1}"
LOCAL_RUNTIME_DIR="${MISSION_CONTROL_RUNTIME_DIR:-$REPO_DIR/.runtime-local}"
LOCAL_INSTANCE_PATH="${MISSION_CONTROL_INSTANCE_PATH:-$REPO_DIR/.instance-local}"
LOCAL_DISPATCHER_EXECUTOR="${MISSION_CONTROL_DISPATCHER_EXECUTOR:-crewai}"

# Crear directorio de logs si no existe
mkdir -p "$LOG_DIR"
mkdir -p "$LOCAL_RUNTIME_DIR"
mkdir -p "$LOCAL_INSTANCE_PATH"

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

ensure_local_python() {
    if [ ! -x "$PYTHON_BIN" ] && [ "${AUTO_BOOTSTRAP_LOCAL_ENV}" = "1" ]; then
        echo "📦 Preparando entorno local Python ${TARGET_PYTHON_VERSION}..."
        bash "$REPO_DIR/scripts/bootstrap_local_env.sh"
    fi

    if [ ! -x "$PYTHON_BIN" ]; then
        echo "❌ No se encontró Python virtualenv en $PYTHON_BIN"
        echo "Ejecuta ./scripts/bootstrap_local_env.sh o exporta PYTHON_BIN antes de ejecutar."
        exit 1
    fi

    CURRENT_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [ "$CURRENT_VERSION" != "$TARGET_PYTHON_VERSION" ]; then
        if [ "${AUTO_BOOTSTRAP_LOCAL_ENV}" = "1" ] && [ "$PYTHON_BIN" = "$REPO_DIR/.venv/bin/python" ]; then
            echo "📦 Reemplazando virtualenv local Python ${CURRENT_VERSION} por ${TARGET_PYTHON_VERSION}..."
            bash "$REPO_DIR/scripts/bootstrap_local_env.sh"
            CURRENT_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        fi

        if [ "$CURRENT_VERSION" != "$TARGET_PYTHON_VERSION" ]; then
            echo "❌ Python local incompatible: ${CURRENT_VERSION}"
            echo "Mission Control requiere Python ${TARGET_PYTHON_VERSION} para CrewAI."
            exit 1
        fi
    fi
}

# Verificar dependencias
ensure_local_python

if ! "$PYTHON_BIN" -m pip list | grep -q Flask; then
    echo "📦 Instalando dependencias..."
    "$PYTHON_BIN" -m pip install -r requirements-dev.txt
fi

# Iniciar servidor en background
echo "🚀 Iniciando Mission Control..."
nohup env PORT="$PORT" MISSION_CONTROL_RUNTIME_DIR="$LOCAL_RUNTIME_DIR" MISSION_CONTROL_INSTANCE_PATH="$LOCAL_INSTANCE_PATH" MISSION_CONTROL_DISPATCHER_EXECUTOR="$LOCAL_DISPATCHER_EXECUTOR" "$PYTHON_BIN" app.py > "$LOG_DIR/mission_control.log" 2>&1 &
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
        echo "🗃️  Instance local: $LOCAL_INSTANCE_PATH"
        echo "🗂️  Runtime local: $LOCAL_RUNTIME_DIR"
        echo "🤖 Dispatcher local: $LOCAL_DISPATCHER_EXECUTOR"
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
