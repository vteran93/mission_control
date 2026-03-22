#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

print_json() {
    python3 -m json.tool
}

docker compose up -d --build app

for _ in $(seq 1 60); do
    CONTAINER_ID="$(docker compose ps -q app 2>/dev/null || true)"
    STATUS=""
    if [ -n "${CONTAINER_ID}" ]; then
        STATUS="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${CONTAINER_ID}" 2>/dev/null || true)"
    fi
    if [ "${STATUS}" = "healthy" ]; then
        break
    fi
    sleep 2
done

docker compose ps -a
curl -fsS "http://127.0.0.1:5001/api/health" | print_json
curl -fsS "http://127.0.0.1:5001/api/runtime/health" | print_json
curl -fsS "http://127.0.0.1:5001/api/runtime/crew-seeds" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
json.dump(sorted(payload.keys()), sys.stdout, indent=2)
sys.stdout.write("\n")
'

echo "Smoke docker OK en http://127.0.0.1:5001"
