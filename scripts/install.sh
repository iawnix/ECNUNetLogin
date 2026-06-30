#!/usr/bin/env bash
# Install auth_ecnu into a local Python virtualenv.
#
# Usage:
#   ./scripts/install.sh                 # creates .venv next to the repo
#   AUTH_ECNU_VENV=/opt/auth ./scripts/install.sh
#   AUTH_ECNU_PYTHON=python3.11 ./scripts/install.sh
#
# After install:
#   source .venv/bin/activate            # POSIX shells
#   . .venv/bin/activate.fish            # fish
#   auth_ecnu --version
#
# This script does not require conda and only uses stdlib `venv` + pip.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${AUTH_ECNU_VENV:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${AUTH_ECNU_PYTHON:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} is not available; install Python >= 3.10 first" >&2
  exit 127
fi

PY_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_OK="$("${PYTHON_BIN}" -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')"
if [ "${PY_OK}" != "1" ]; then
  echo "error: auth_ecnu requires Python >= 3.10 (found ${PY_VERSION})" >&2
  exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
  echo "creating venv: ${VENV_DIR} (python ${PY_VERSION})"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
  echo "reusing existing venv: ${VENV_DIR}"
fi

# shellcheck disable=SC1091
"${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
"${VENV_DIR}/bin/python" -m pip install -e "${ROOT_DIR}"

cat <<EOF

Installed auth_ecnu into venv: ${VENV_DIR}

Activate it with one of:
  source ${VENV_DIR}/bin/activate         # bash/zsh
  . ${VENV_DIR}/bin/activate.fish         # fish

Or run the entry point directly without activating:
  ${VENV_DIR}/bin/auth_ecnu --version

For a global, isolated install consider pipx:
  pipx install ${ROOT_DIR}
EOF
