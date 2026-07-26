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
#
# If you *just* ran setup/linux.sh or setup/macos.sh in this terminal, your
# shell may not have picked up the newly-installed tools yet. We probe the
# standard install dirs (~/.local/bin, ~/.cargo/bin, /opt/homebrew/bin,
# /usr/local/bin) as a fallback so a fresh install works immediately. If that
# still fails, OPEN A NEW TERMINAL so your shell sources its updated PATH.
set -euo pipefail
cd "$(dirname "$0")"

# --- resolve tool locations (PATH first, then known install dirs) ----------
resolve_tool() {
    # resolve_tool <name> — echoes the path to stdout, returns 1 if not found.
    local tool="$1" d
    command -v "$tool" 2>/dev/null && return 0
    case "$(uname -s)" in
        Darwin)
            for d in "$HOME/.local/bin" "$HOME/.cargo/bin" \
                     /opt/homebrew/bin /usr/local/bin; do
                [[ -x "$d/$tool" ]] && { echo "$d/$tool"; return 0; }
            done ;;
        *)
            for d in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
                [[ -x "$d/$tool" ]] && { echo "$d/$tool"; return 0; }
            done ;;
    esac
    return 1
}

# Source cargo/homebrew env files if present (also helps a fresh shell pick up
# PATH entries from a just-finished installer).
[[ -r "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"

UV_BIN=""
if UV_BIN="$(resolve_tool uv 2>/dev/null)"; then
    # Make sure start.py (and the venv it creates) can see cargo too.
    if CARGO_BIN="$(resolve_tool cargo 2>/dev/null)"; then
        export PATH="$(dirname "$CARGO_BIN"):$PATH"
    fi
    exec "$UV_BIN" run python start.py "$@"
fi

# Fallback: a pre-existing .venv (e.g. created by an earlier run).
ROOT="$(pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
    exec "$ROOT/.venv/bin/python" start.py "$@"
fi

cat >&2 <<EOF

uv was not found on PATH or in any standard install location.

You probably need to install it first — the easiest way is the one-time setup
script for your platform:

    bash setup/linux.sh        # Linux (auto-detects distro)
    bash setup/macos.sh        # macOS

Or install uv directly:
    curl -LsSf https://astral.sh/uv/install.sh | sh

If you JUST ran the setup script in this terminal, close it and OPEN A NEW
TERMINAL before trying ./start.sh again — your shell needs to re-read its
PATH to see the tools that were installed.
EOF
exit 1
