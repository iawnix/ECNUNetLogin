#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${AUTH_ECNU_ENV:-auth-ecnu}"

if ! command -v conda >/dev/null 2>&1; then
  echo "error: conda is not available in PATH" >&2
  exit 127
fi

if conda env list | awk '{print $1}' | grep -Fxq "${ENV_NAME}"; then
  conda env update -n "${ENV_NAME}" -f "${ROOT_DIR}/environment.yml" --prune
else
  conda env create -n "${ENV_NAME}" -f "${ROOT_DIR}/environment.yml"
fi

conda run -n "${ENV_NAME}" python -m pip install -e "${ROOT_DIR}"
conda run -n "${ENV_NAME}" auth_ecnu -h

cat <<EOF

Installed auth_ecnu into conda environment: ${ENV_NAME}

Run:
  conda activate ${ENV_NAME}
  auth_ecnu -h
EOF
