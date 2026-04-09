#!/usr/bin/env bash
# Run the Momir app with ~/momir-venv.
# The mouse helper is expected to keep running in the background and will
# automatically enter standby while Momir owns the runtime lock.
#
# Usage (from repo root or anywhere):
#   bash /path/to/The-Momir-Machine/scripts/run-momir.sh
#
# Override paths if yours differ:
#   MOMIR_APP=/path/to/app.py MOMIR_PYTHON=~/momir-venv/bin/python bash scripts/run-momir.sh
# If root privileges are needed (for printer access), this script can relaunch
# itself with sudo and preserve the needed environment variables.

set -euo pipefail

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo --preserve-env=DISPLAY,XAUTHORITY,WAYLAND_DISPLAY,MOMIR_PYTHON,MOMIR_APP /usr/bin/env bash "${SCRIPT_PATH}" "$@"
fi

MOMIR_USER_HOME="${HOME}"
if [[ -n "${SUDO_USER:-}" ]]; then
  MOMIR_USER_HOME="$(eval echo "~${SUDO_USER}")"
fi

MOMIR_PYTHON="${MOMIR_PYTHON:-${MOMIR_USER_HOME}/momir-venv/bin/python}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOMIR_APP="${MOMIR_APP:-${SCRIPT_DIR}/../app.py}"

if [[ ! -x "${MOMIR_PYTHON}" ]]; then
  echo "run-momir: Momir venv Python not found or not executable: ${MOMIR_PYTHON}" >&2
  exit 1
fi

MOMIR_APP="$(cd "$(dirname "${MOMIR_APP}")" && pwd)/$(basename "${MOMIR_APP}")"
if [[ ! -f "${MOMIR_APP}" ]]; then
  echo "run-momir: app not found: ${MOMIR_APP}" >&2
  exit 1
fi

"${MOMIR_PYTHON}" "${MOMIR_APP}" "$@"
