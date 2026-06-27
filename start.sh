#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv &>/dev/null; then
    echo "uv not found. Install from https://docs.astral.sh/uv/"
    exit 1
fi

uv run src/start.py --web
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    read -n 1 -p "Press any key to exit..."
fi
exit $EXIT_CODE
