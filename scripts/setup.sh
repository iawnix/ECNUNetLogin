#!/usr/bin/env bash
# auth_ecnu unified installer / uninstaller.
#
# Single entry point for installing auth_ecnu via pipx, venv, or
# pip install --user. Records the chosen layout in a state file so
# uninstall can undo exactly what install did.
#
# Quick usage:
#   ./scripts/setup.sh install        interactive
#   ./scripts/setup.sh install --method=pipx --host=172.20.20.11 --yes
#   ./scripts/setup.sh status
#   ./scripts/setup.sh uninstall --purge --yes
#
# See `./scripts/setup.sh --help` for all options.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROG="$(basename "${BASH_SOURCE[0]}")"

# XDG paths (POSIX). Windows users should install via pipx in a real shell.
XDG_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/auth_ecnu"
STATE_FILE="$XDG_CONFIG_DIR/install-state"
DEFAULT_CONFIG_FILE="$XDG_CONFIG_DIR/setting"

# Defaults / flag-driven values
METHOD=""
INSTALL_PATH=""
CONFIG_PATH="$DEFAULT_CONFIG_FILE"
HOST=""
ACID=""
CAMPUS_POSTFIX=""
CAMPUS_URL=""
NON_INTERACTIVE=0
PURGE=0

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

c_red()    { printf '\033[1;31m%s\033[0m' "$1"; }
c_green()  { printf '\033[1;32m%s\033[0m' "$1"; }
c_cyan()   { printf '\033[36m%s\033[0m' "$1"; }
c_dim()    { printf '\033[2m%s\033[0m' "$1"; }

info() { printf '%s %s\n' "$(c_green '>')"  "$*"; }
warn() { printf '%s %s\n' "$(c_red   '!')" "$*" >&2; }
die()  { warn "$@"; exit 2; }

prompt() {
  # prompt VAR_NAME PROMPT_TEXT DEFAULT
  local var=$1 text=$2 default=${3:-} value
  if [ "$NON_INTERACTIVE" = 1 ]; then
    printf -v "$var" '%s' "$default"
    return
  fi
  if [ -n "$default" ]; then
    printf '  %s [%s]: ' "$text" "$default"
  else
    printf '  %s: ' "$text"
  fi
  read -r value || true
  if [ -z "$value" ]; then
    value=$default
  fi
  printf -v "$var" '%s' "$value"
}

usage() {
  cat <<EOF
auth_ecnu installer

Usage:
  $PROG install   [options]   install auth_ecnu (interactive by default)
  $PROG uninstall [options]   uninstall auth_ecnu
  $PROG status                show current install information
  $PROG --help                this help

Install options:
  --method=pipx|venv|user     install backend (default: prompted)
                                pipx — isolated, globally available
                                venv — project-local .venv (this repo)
                                user — pip install --user into ~/.local
  --install-path=PATH         venv directory (venv method only;
                                default: \$ROOT/.venv)
  --config-path=PATH          config file location
                                (default: $DEFAULT_CONFIG_FILE)
  --host=HOST                 initial portal host (e.g. 172.20.20.11)
  --acid=N                    initial ac_id (default: 1)
  --campus-postfix=SFX        initial campus_postfix (empty by default)
  --campus-url=URL            initial campus_url (empty by default)
  --yes                       non-interactive; fail if required values
                                are missing instead of prompting

Uninstall options:
  --purge                     also remove config file and install-state
  --yes                       skip confirmation prompts

Security: the installer never asks for username or password. Those are
passed at runtime via -u / --ask-password / --password-stdin, or via a
--in-json file you control. See docs/config.md.
EOF
}

# Parse \`key=value\` style flags
parse_flag() {
  local raw=$1
  case "$raw" in
    --method=*)         METHOD=${raw#*=} ;;
    --install-path=*)   INSTALL_PATH=${raw#*=} ;;
    --config-path=*)    CONFIG_PATH=${raw#*=} ;;
    --host=*)           HOST=${raw#*=} ;;
    --acid=*)           ACID=${raw#*=} ;;
    --campus-postfix=*) CAMPUS_POSTFIX=${raw#*=} ;;
    --campus-url=*)     CAMPUS_URL=${raw#*=} ;;
    --yes|-y)           NON_INTERACTIVE=1 ;;
    --purge)            PURGE=1 ;;
    -h|--help)          usage; exit 0 ;;
    *)                  die "unknown option: $raw" ;;
  esac
}

require_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    die "python3 is required but not found in PATH"
  fi
  local py_ok
  py_ok=$(python3 -c 'import sys; print(1 if sys.version_info>=(3,10) else 0)')
  if [ "$py_ok" != "1" ]; then
    die "auth_ecnu needs Python >= 3.10 (found $(python3 -V 2>&1))"
  fi
}

check_method_available() {
  case "$METHOD" in
    pipx)
      if ! command -v pipx >/dev/null 2>&1; then
        die "method=pipx requested but 'pipx' is not installed. \
Install it (e.g. 'python3 -m pip install --user pipx && pipx ensurepath') and try again."
      fi
      ;;
    venv)
      if ! python3 -c 'import venv' >/dev/null 2>&1; then
        die "method=venv requested but the stdlib 'venv' module is unavailable. \
Install python3-venv (Debian/Ubuntu: 'apt install python3-venv') and try again."
      fi
      ;;
    user)
      if ! command -v pip3 >/dev/null 2>&1 && ! command -v pip >/dev/null 2>&1; then
        die "method=user requested but no 'pip' found. \
Install python3-pip and try again."
      fi
      ;;
    *)
      die "unknown method: ${METHOD:-<empty>}. Choose one of: pipx, venv, user."
      ;;
  esac
}

choose_method_interactive() {
  cat <<EOF

$(c_green '>') Install method:
  1) pipx    isolated, globally available CLI (recommended for end users)
  2) venv    project-local virtualenv in $ROOT_DIR/.venv (recommended for dev)
  3) user    pip install --user into ~/.local (no virtualenv)
EOF
  prompt _PICK "  Choose 1/2/3" "1"
  case "$_PICK" in
    1|pipx) METHOD=pipx ;;
    2|venv) METHOD=venv ;;
    3|user) METHOD=user ;;
    *)      die "invalid choice: $_PICK" ;;
  esac
}

# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

write_config() {
  mkdir -p "$(dirname "$CONFIG_PATH")"
  if [ -e "$CONFIG_PATH" ] && [ "$NON_INTERACTIVE" != 1 ]; then
    prompt _OVR "config file $CONFIG_PATH exists; overwrite? (y/N)" "n"
    case "$_OVR" in
      y|Y|yes|YES) : ;;
      *) info "leaving existing config in place: $CONFIG_PATH"; return ;;
    esac
  fi
  cat > "$CONFIG_PATH" <<EOF
# auth_ecnu setting file
# Generated by setup.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
#
# WARNING: do not store passwords or other credentials here.
# Pass --username/-u at runtime, or use 'auth_ecnu --in-json file.json'
# with a file you keep private (mode 600).

host="$HOST"
acid="$ACID"
campus_postfix="$CAMPUS_POSTFIX"
campus_url="$CAMPUS_URL"
EOF
  chmod 600 "$CONFIG_PATH"
  info "wrote config: $CONFIG_PATH (mode 600)"
}

write_state() {
  local resolved_install_path=$1
  mkdir -p "$(dirname "$STATE_FILE")"
  cat > "$STATE_FILE" <<EOF
method=$METHOD
install_path=$resolved_install_path
config_path=$CONFIG_PATH
package_root=$ROOT_DIR
installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
version=$(python3 -c "import re,sys; sys.path.insert(0, '$ROOT_DIR/src'); from auth_ecnu import __version__; print(__version__)")
EOF
  chmod 600 "$STATE_FILE"
}

do_install_pipx() {
  info "installing via pipx (source: $ROOT_DIR)"
  pipx install --force "$ROOT_DIR"
  # pipx exposes the venv path via 'pipx environment'; fall back to a guess.
  local venv_path
  venv_path=$(pipx environment --value PIPX_LOCAL_VENVS 2>/dev/null)/auth-ecnu
  write_state "$venv_path"
  cat <<EOF

$(c_green 'done.') Try:
  auth_ecnu --version
  auth_ecnu check
EOF
}

do_install_venv() {
  local venv=${INSTALL_PATH:-$ROOT_DIR/.venv}
  info "creating venv at $venv"
  if [ ! -d "$venv" ]; then
    python3 -m venv "$venv"
  fi
  "$venv/bin/python" -m pip install --quiet --upgrade pip
  "$venv/bin/python" -m pip install -e "$ROOT_DIR"
  write_state "$venv"
  cat <<EOF

$(c_green 'done.') Activate and try:
  source $venv/bin/activate
  auth_ecnu --version
  auth_ecnu check

Or run without activating:
  $venv/bin/auth_ecnu check
EOF
}

do_install_user() {
  info "installing via pip install --user"
  python3 -m pip install --user -e "$ROOT_DIR"
  # ~/.local/bin should be on PATH; use it as the recorded install_path.
  write_state "$HOME/.local"
  cat <<EOF

$(c_green 'done.') Make sure $HOME/.local/bin is in your PATH, then try:
  auth_ecnu --version
  auth_ecnu check
EOF
}

do_install() {
  require_python

  cat <<EOF
auth_ecnu installer
═══════════════════

EOF

  if [ -z "$METHOD" ]; then
    if [ "$NON_INTERACTIVE" = 1 ]; then
      die "--method is required when --yes is set"
    fi
    choose_method_interactive
  fi
  check_method_available

  # Config path
  if [ "$NON_INTERACTIVE" != 1 ]; then
    prompt CONFIG_PATH "Config file location" "$CONFIG_PATH"
  fi
  # Initial portal values
  if [ "$NON_INTERACTIVE" != 1 ]; then
    info "Initial portal config (credentials must NEVER be entered here):"
    prompt HOST           "host (e.g. 172.20.20.11)" "$HOST"
    prompt ACID           "ac_id" "${ACID:-1}"
    prompt CAMPUS_POSTFIX "campus_postfix (often empty)" "$CAMPUS_POSTFIX"
  fi
  [ -z "$ACID" ] && ACID=1

  write_config

  case "$METHOD" in
    pipx) do_install_pipx ;;
    venv) do_install_venv ;;
    user) do_install_user ;;
  esac
}

# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

read_state() {
  if [ ! -f "$STATE_FILE" ]; then
    return 1
  fi
  local key value
  while IFS='=' read -r key value; do
    case "$key" in
      method)        S_METHOD=$value ;;
      install_path)  S_INSTALL_PATH=$value ;;
      config_path)   S_CONFIG_PATH=$value ;;
      package_root)  S_PACKAGE_ROOT=$value ;;
      installed_at)  S_INSTALLED_AT=$value ;;
      version)       S_VERSION=$value ;;
    esac
  done < "$STATE_FILE"
  return 0
}

do_uninstall() {
  if ! read_state; then
    warn "no install-state at $STATE_FILE; nothing to do."
    warn "if you installed manually, remove the package by hand:"
    warn "  pipx uninstall auth-ecnu     (if pipx)"
    warn "  rm -rf <your-venv>           (if venv)"
    warn "  pip uninstall -y auth-ecnu   (if pip --user)"
    exit 0
  fi

  cat <<EOF
auth_ecnu uninstaller
═════════════════════
  method:        $S_METHOD
  install path:  $S_INSTALL_PATH
  config path:   $S_CONFIG_PATH
  installed at:  $S_INSTALLED_AT
  version:       $S_VERSION

EOF

  if [ "$NON_INTERACTIVE" != 1 ]; then
    prompt _CONF "Proceed with uninstall? (y/N)" "n"
    case "$_CONF" in y|Y|yes|YES) : ;; *) info "aborted."; exit 0 ;; esac
  fi

  case "$S_METHOD" in
    pipx)
      if command -v pipx >/dev/null 2>&1; then
        pipx uninstall auth-ecnu || warn "pipx uninstall failed (already removed?)"
      else
        warn "pipx not in PATH; skip"
      fi
      ;;
    venv)
      if [ -d "$S_INSTALL_PATH" ]; then
        info "removing venv: $S_INSTALL_PATH"
        rm -rf "$S_INSTALL_PATH"
      fi
      ;;
    user)
      python3 -m pip uninstall -y auth-ecnu || warn "pip uninstall failed (already removed?)"
      ;;
    *)
      warn "unknown method '$S_METHOD' in state file; nothing to remove"
      ;;
  esac

  if [ "$PURGE" = "1" ]; then
    if [ -f "$S_CONFIG_PATH" ]; then
      info "removing config: $S_CONFIG_PATH"
      rm -f "$S_CONFIG_PATH"
    fi
    info "removing state: $STATE_FILE"
    rm -f "$STATE_FILE"
    # Best-effort: drop empty XDG dir.
    rmdir "$XDG_CONFIG_DIR" 2>/dev/null || true
  else
    info "config left in place: $S_CONFIG_PATH"
    info "state left in place: $STATE_FILE (rerun with --purge to remove)"
  fi
  info "done."
}

# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

do_status() {
  if read_state; then
    cat <<EOF
auth_ecnu install status
════════════════════════
  method:        $S_METHOD
  install path:  $S_INSTALL_PATH
  config path:   $S_CONFIG_PATH
  installed at:  $S_INSTALLED_AT
  version:       $S_VERSION
EOF
    if [ -f "$S_CONFIG_PATH" ]; then
      printf '  config file:   %s (present)\n' "$S_CONFIG_PATH"
    else
      printf '  config file:   %s (missing)\n' "$S_CONFIG_PATH"
    fi
  else
    warn "no install-state at $STATE_FILE"
    warn "auth_ecnu was either never installed via setup.sh, or already uninstalled."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------

COMMAND="${1:-}"
if [ -n "$COMMAND" ]; then
  shift
fi
for arg in "$@"; do
  parse_flag "$arg"
done

case "$COMMAND" in
  install)   do_install ;;
  uninstall) do_uninstall ;;
  status)    do_status ;;
  -h|--help|help) usage ;;
  ""|*)      usage; exit 2 ;;
esac
