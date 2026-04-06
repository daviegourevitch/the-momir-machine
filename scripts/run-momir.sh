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

set -euo pipefail

MOMIR_PYTHON="${MOMIR_PYTHON:-${HOME}/momir-venv/bin/python}"

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
