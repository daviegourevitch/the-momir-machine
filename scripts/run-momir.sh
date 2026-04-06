#!/usr/bin/env bash
# Run the Momir app with ~/momir-venv, stopping the Waveshare HAT mouse helper first
# so GPIO is not shared (see documentation/MOUSE_FROM_SCRATCH.md). Restarts the mouse
# when Momir exits (normal exit, Ctrl+C, or crash — not SIGKILL).
#
# Usage (from repo root or anywhere):
#   bash /path/to/The-Momir-Machine/scripts/run-momir.sh
#
# Override paths if yours differ:
#   MOMIR_APP=/path/to/app.py MOUSE_SCRIPT=/path/to/mouse.py MOUSE_PYTHON=~/waveshare-mouse-venv/bin/python bash scripts/run-momir.sh

set -euo pipefail

MOMIR_PYTHON="${MOMIR_PYTHON:-${HOME}/momir-venv/bin/python}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOMIR_APP="${MOMIR_APP:-${SCRIPT_DIR}/../app.py}"

# Default mouse helper paths from documentation/MOUSE_FROM_SCRATCH.md — change via env if needed.
MOUSE_PYTHON="${MOUSE_PYTHON:-${HOME}/waveshare-mouse-venv/bin/python}"
MOUSE_SCRIPT="${MOUSE_SCRIPT:-${HOME}/Code/waveshare-mouse/mouse.py}"

DISPLAY="${DISPLAY:-:0}"
XAUTHORITY="${XAUTHORITY:-${HOME}/.Xauthority}"

MOUSE_RESTART="${MOUSE_RESTART:-1}"

stop_mouse() {
  if [[ -n "${MOUSE_SCRIPT}" ]] && [[ -f "${MOUSE_SCRIPT}" ]]; then
    pkill -f "${MOUSE_SCRIPT}" 2>/dev/null || true
  else
    pkill -f '[ /]mouse\.py' 2>/dev/null || true
  fi
}

start_mouse() {
  if [[ "${MOUSE_RESTART}" != "1" ]]; then
    return 0
  fi
  if [[ ! -f "${MOUSE_SCRIPT}" ]]; then
    echo "run-momir: MOUSE_SCRIPT not found (${MOUSE_SCRIPT}); not restarting mouse." >&2
    return 0
  fi
  if [[ ! -x "${MOUSE_PYTHON}" ]]; then
    echo "run-momir: MOUSE_PYTHON not executable (${MOUSE_PYTHON}); not restarting mouse." >&2
    return 0
  fi
  nohup env DISPLAY="${DISPLAY}" XAUTHORITY="${XAUTHORITY}" \
    "${MOUSE_PYTHON}" "${MOUSE_SCRIPT}" >/dev/null 2>&1 &
  disown 2>/dev/null || true
}

cleanup() {
  start_mouse
}
trap cleanup EXIT

if [[ ! -x "${MOMIR_PYTHON}" ]]; then
  echo "run-momir: Momir venv Python not found or not executable: ${MOMIR_PYTHON}" >&2
  exit 1
fi

MOMIR_APP="$(cd "$(dirname "${MOMIR_APP}")" && pwd)/$(basename "${MOMIR_APP}")"
if [[ ! -f "${MOMIR_APP}" ]]; then
  echo "run-momir: app not found: ${MOMIR_APP}" >&2
  exit 1
fi

stop_mouse
# Brief pause so the OS / drivers release lines before gpiozero opens them.
sleep 0.25

# Do not use `exec` here — the shell must remain so the EXIT trap can restart the mouse.
"${MOMIR_PYTHON}" "${MOMIR_APP}" "$@"
