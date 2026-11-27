#!/bin/bash
set -eu

lab_root="$(cd -- "$(dirname -- "$0")" && pwd)"
export ROBOT_LAB_ROOT="$lab_root"
export PYTHONPATH="$lab_root/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Robot Lab requires Python 3.9 or newer.'
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
    printf '%s\n' 'Robot Lab requires Python 3.9 or newer.'
    exit 1
fi

if [ -z "${ROBOT_LAB_CONFIG:-}" ] && [ -f "$lab_root/configs/local.json" ]; then
    export ROBOT_LAB_CONFIG="$lab_root/configs/local.json"
fi

exec python3 -m robot_platform.cli "$@"
