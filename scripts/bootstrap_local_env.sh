#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_VERSION="${TARGET_VERSION:-3.12}"
VENV_DIR="${VENV_DIR:-$REPO_DIR/.venv}"
BACKUP_ROOT="${BACKUP_ROOT:-${TMPDIR:-/tmp}/mission_control-venv-backups}"
REINSTALL_DEPS="${REINSTALL_DEPS:-1}"

find_python_bin() {
    if [ -n "${PYTHON312_BIN:-}" ] && [ -x "${PYTHON312_BIN}" ]; then
        printf '%s\n' "${PYTHON312_BIN}"
        return 0
    fi

    if command -v "python${TARGET_VERSION}" >/dev/null 2>&1; then
        command -v "python${TARGET_VERSION}"
        return 0
    fi

    if command -v uv >/dev/null 2>&1; then
        uv python install "${TARGET_VERSION}" >/dev/null
        uv python find "${TARGET_VERSION}"
        return 0
    fi

    return 1
}

create_virtualenv() {
    if "${TARGET_PYTHON_BIN}" -m venv "${VENV_DIR}"; then
        return 0
    fi

    rm -rf "${VENV_DIR}"

    if command -v uv >/dev/null 2>&1; then
        echo "Fallo python -m venv; intentando uv venv con ${TARGET_PYTHON_BIN}"
        uv venv --seed --python "${TARGET_PYTHON_BIN}" "${VENV_DIR}"
        return 0
    fi

    echo "No fue posible crear la virtualenv con ${TARGET_PYTHON_BIN}."
    exit 1
}

TARGET_PYTHON_BIN="$(find_python_bin || true)"
if [ -z "${TARGET_PYTHON_BIN}" ]; then
    echo "No se encontro un interprete Python ${TARGET_VERSION}."
    echo "Instala python${TARGET_VERSION} o uv antes de continuar."
    exit 1
fi

mkdir -p "${BACKUP_ROOT}"

if [ -x "${VENV_DIR}/bin/python" ]; then
    CURRENT_VERSION="$("${VENV_DIR}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [ "${CURRENT_VERSION}" != "${TARGET_VERSION}" ]; then
        BACKUP_DIR="${BACKUP_ROOT}/venv-${CURRENT_VERSION//./_}-$(date +%Y%m%d%H%M%S)"
        echo "Moviendo venv existente (${CURRENT_VERSION}) a ${BACKUP_DIR}"
        mv "${VENV_DIR}" "${BACKUP_DIR}"
    fi
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "Creando virtualenv local con ${TARGET_PYTHON_BIN}"
    create_virtualenv
fi

if ! "${VENV_DIR}/bin/python" -m pip --version >/dev/null 2>&1; then
    echo "Virtualenv sin pip funcional; recreando ${VENV_DIR}"
    rm -rf "${VENV_DIR}"
    create_virtualenv
fi

if [ "${REINSTALL_DEPS}" = "1" ]; then
    "${VENV_DIR}/bin/python" -m pip install --upgrade pip
    "${VENV_DIR}/bin/python" -m pip install -r "${REPO_DIR}/requirements-dev.txt"
fi

echo "Bootstrap local completado."
echo "Python local: $("${VENV_DIR}/bin/python" --version)"
echo "Virtualenv: ${VENV_DIR}"
