#!/usr/bin/env bash
# Uninstall auth_ecnu. Removes the project venv and (optionally) the
# user config file. Idempotent.
#
# Usage:
#   ./scripts/uninstall.sh                # remove the project .venv
#   ./scripts/uninstall.sh --purge        # also remove ~/.auth-setting
#   AUTH_ECNU_VENV=/opt/auth ./scripts/uninstall.sh
#
# If you installed via pipx instead, run `pipx uninstall auth-ecnu`.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${AUTH_ECNU_VENV:-${ROOT_DIR}/.venv}"
PURGE=0

for arg in "$@"; do
  case "${arg}" in
    --purge) PURGE=1 ;;
    -h|--help)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "error: unknown argument: ${arg}" >&2
      exit 2
      ;;
  esac
done

if [ -d "${VENV_DIR}" ]; then
  echo "removing venv: ${VENV_DIR}"
  rm -rf "${VENV_DIR}"
else
  echo "no venv at ${VENV_DIR} (already removed)"
fi

if [ "${PURGE}" = "1" ]; then
  CONFIG="${HOME}/.auth-setting"
  if [ -f "${CONFIG}" ]; then
    echo "removing config: ${CONFIG}"
    rm -f "${CONFIG}"
  else
    echo "no config at ${CONFIG}"
  fi
fi

echo "done."
