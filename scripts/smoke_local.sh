#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
PORT="${PORT:-5011}"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/smoke_local.log"
TARGET_PYTHON_VERSION="${TARGET_PYTHON_VERSION:-3.12}"
LOCAL_RUNTIME_DIR="${MISSION_CONTROL_RUNTIME_DIR:-$REPO_DIR/.runtime-local}"
LOCAL_INSTANCE_PATH="${MISSION_CONTROL_INSTANCE_PATH:-$REPO_DIR/.instance-local}"
LOCAL_DISPATCHER_EXECUTOR="${MISSION_CONTROL_DISPATCHER_EXECUTOR:-crewai}"

print_json() {
    "${PYTHON_BIN}" -m json.tool
}

mkdir -p "${LOG_DIR}"
mkdir -p "${LOCAL_RUNTIME_DIR}"
mkdir -p "${LOCAL_INSTANCE_PATH}"

if [ ! -x "${PYTHON_BIN}" ]; then
    echo "Preparando entorno local Python ${TARGET_PYTHON_VERSION}..."
    bash "${REPO_DIR}/scripts/bootstrap_local_env.sh"
fi

CURRENT_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "${CURRENT_VERSION}" != "${TARGET_PYTHON_VERSION}" ]; then
    echo "Corrigiendo virtualenv local Python ${CURRENT_VERSION} -> ${TARGET_PYTHON_VERSION}..."
    bash "${REPO_DIR}/scripts/bootstrap_local_env.sh"
fi

cleanup() {
    if [ -n "${SERVER_PID:-}" ] && ps -p "${SERVER_PID}" >/dev/null 2>&1; then
        kill "${SERVER_PID}" >/dev/null 2>&1 || true
        wait "${SERVER_PID}" 2>/dev/null || true
    fi
}

trap cleanup EXIT

cd "${REPO_DIR}"
env FLASK_DEBUG=false PORT="${PORT}" MISSION_CONTROL_RUNTIME_DIR="${LOCAL_RUNTIME_DIR}" MISSION_CONTROL_INSTANCE_PATH="${LOCAL_INSTANCE_PATH}" MISSION_CONTROL_DISPATCHER_EXECUTOR="${LOCAL_DISPATCHER_EXECUTOR}" "${PYTHON_BIN}" app.py > "${LOG_FILE}" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

curl -fsS "http://127.0.0.1:${PORT}/api/health" | print_json
curl -fsS "http://127.0.0.1:${PORT}/api/runtime/health" | print_json
curl -fsS "http://127.0.0.1:${PORT}/api/runtime/tools" | "${PYTHON_BIN}" -c '
import json
import sys

payload = json.load(sys.stdin)
json.dump([item["name"] for item in payload], sys.stdout, indent=2)
sys.stdout.write("\n")
'

echo "Smoke local OK en http://127.0.0.1:${PORT}"
echo "Instance local OK en ${LOCAL_INSTANCE_PATH}"
echo "Runtime local OK en ${LOCAL_RUNTIME_DIR}"
echo "Dispatcher local OK en ${LOCAL_DISPATCHER_EXECUTOR}"
