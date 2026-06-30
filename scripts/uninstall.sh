#!/usr/bin/env bash
# Uninstall auth_ecnu. Removes the project venv and (optionally) any
# stored config files. Idempotent.
#
# Usage:
#   ./scripts/uninstall.sh                # remove the project .venv
#   ./scripts/uninstall.sh --purge        # also remove config files
#   AUTH_ECNU_VENV=/opt/auth ./scripts/uninstall.sh
#
# --purge removes both the new XDG/AppData config and the legacy
# ~/.auth-setting if either exists.
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
      sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
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
  XDG_CONFIG_HOME_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}"
  TARGETS=(
    "${XDG_CONFIG_HOME_DIR}/auth_ecnu/setting"
    "${HOME}/.auth-setting"
  )
  for target in "${TARGETS[@]}"; do
    if [ -f "${target}" ]; then
      echo "removing config: ${target}"
      rm -f "${target}"
    fi
  done
  # Best-effort: drop the now-empty auth_ecnu dir.
  rmdir "${XDG_CONFIG_HOME_DIR}/auth_ecnu" 2>/dev/null || true
fi

echo "done."
