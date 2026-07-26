#!/usr/bin/env bash
# PalworldSaveTools launcher (macOS / Linux).
#
# Thin wrapper around start.py — the real bootstrap (venv, submodules, port
# freeing, preflight, frontend + backend + optional Tauri orchestration) lives
# there. Pass --web for browser mode; pass --check to run only the preflight.
#
#   ./start.sh            native Tauri window
#   ./start.sh --web      browser mode (no native window)
#   ./start.sh --check    run only the environment check
set -euo pipefail
cd "$(dirname "$0")"

if command -v uv >/dev/null 2>&1; then
    exec uv run python start.py "$@"
fi

# Fallback: a pre-existing .venv (e.g. created by an earlier run).
ROOT="$(pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
    exec "$ROOT/.venv/bin/python" start.py "$@"
fi

cat >&2 <<EOF
uv not found — it's required to manage PST's Python environment.

Either install uv:
    curl -LsSf https://astral.sh/uv/install.sh | sh

…or run the one-time setup script for your platform first:
    bash setup/macos.sh        # macOS
    bash setup/linux.sh        # Linux (auto-detects distro)
EOF
exit 1
