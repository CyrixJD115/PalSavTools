#!/usr/bin/env bash
# PalworldSaveTools — Debian/Ubuntu setup (apt-based distros).
#   Targets: Ubuntu 24.04+, Linux Mint 22+, Debian 12+, Pop!_OS, etc.
#
# Installs every system dependency needed to *build and launch* PST from source:
# Python venv, Rust (cargo), Node.js, uv, plus the GTK/WebKit dev headers Tauri
# needs on Linux. Safe to re-run — every step is idempotent and verifies the
# tool actually works before moving on.
#
# See setup/README.md for what each package is for and troubleshooting.
set -euo pipefail

if [[ $EUID -eq 0 ]]; then
    echo "Don't run this as root — it uses sudo only where needed." >&2
    exit 1
fi
command -v sudo >/dev/null || { echo "sudo is required." >&2; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# --- output helpers --------------------------------------------------------
c_ok()   { printf '\033[92m✓\033[0m %s\n' "$*"; }
c_warn() { printf '\033[93m⚠\033[0m %s\n' "$*"; }
c_crit() { printf '\033[91m✗\033[0m %s\n' "$*"; }
c_hint() { printf '    \033[2m→ %s\033[0m\n' "$*"; }
c_info() { printf '\033[96m›\033[0m %s\n' "$*"; }
c_step() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# Verify a tool is on PATH after installing it. Hard-aborts on failure so the
# user knows exactly which step broke instead of seeing a cryptic downstream
# error. Prints the version on success.
verify() {
    local tool="$1" label="$2"
    if have "$tool"; then
        c_ok "$label ($("$tool" --version 2>&1 | head -1))"
        return 0
    fi
    c_crit "$label FAILED — '$tool' still not found on PATH"
    c_hint "Re-run this script, or install $tool manually and re-run."
    c_hint "If you just installed it in this terminal, OPEN A NEW TERMINAL so your PATH refreshes."
    exit 1
}

# Add uv's install dir to PATH (uv installs to ~/.local/bin). Also helps a
# just-finished installer be visible in this same shell.
add_local_bin_to_path() {
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) export PATH="$HOME/.local/bin:$PATH" ;;
    esac
}

banner_new_terminal() {
    # NOTE: use printf with $'...' ANSI-C quoting, NOT a cat<<EOF heredoc.
    # Heredocs emit literal '\033' characters (no escape interpretation), which
    # shows up as raw "\033[1m..." garbage in the terminal.
    local bar=$'\033[1m\033[96m''═══════════════════════════════════════════════════════════'$'\033[0m'
    printf '\n%s\n' "$bar"
    printf '\033[1m  IMPORTANT: open a NEW terminal before running ./start.sh\033[0m\n'
    printf '\033[2m  (so your shell picks up the tools we just installed)\033[0m\n'
    printf '%s\n' "$bar"
}

c_step "1/5  apt system packages"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    ca-certificates \
    git \
    curl \
    wget \
    file \
    python3 \
    python3-dev \
    python3-venv \
    libssl-dev \
    libglib2.0-dev \
    libgtk-3-dev \
    libwebkit2gtk-4.1-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev \
    patchelf
c_ok "system packages installed"

c_step "2/5  Rust toolchain (cargo)"
if have cargo; then
    c_ok "cargo already present ($(cargo --version))"
else
    c_info "installing rustup (rustup.rs)"
    if ! curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
            | sh -s -- -y --profile minimal; then
        c_crit "rustup installer failed to download or run"
        c_hint "Check your network, then re-run this script."
        exit 1
    fi
    [[ -r "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
    verify cargo "Rust install"
fi

c_step "3/5  Node.js LTS + npm"
if have node && have npm; then
    c_ok "node already present ($(node --version))"
else
    c_info "installing Node.js LTS via NodeSource"
    if have curl; then
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    else
        wget -qO- https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    fi
    sudo apt-get install -y nodejs
    verify node "Node.js install"
    verify npm "npm install"
fi

c_step "4/5  uv (Python package manager)"
if have uv; then
    c_ok "uv already present ($(uv --version))"
else
    c_info "installing uv from astral.sh"
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        c_crit "uv installer failed to download or run"
        c_hint "Check your network, then re-run this script."
        exit 1
    fi
    add_local_bin_to_path
    verify uv "uv install"
fi

c_step "5/5  Verify"
cd "$ROOT"
if python3 "$HERE/check_env.py" --mode=launch; then
    c_ok "environment check passed"
else
    rc=$?
    c_warn "check_env.py reported issues (exit $rc) — review the report above."
    c_hint "Critical issues must be fixed before ./start.sh will boot."
fi

banner_new_terminal

# When invoked by get.sh (one-shot installer), skip this summary — get.sh
# prints its own, clearer final instructions. This block only runs when the
# user called setup/linux-*.sh directly.
if [[ -z "${PST_GET_INVOKED:-}" ]]; then
    cat <<EOF

Setup complete. To launch PST (in a NEW terminal so your PATH is refreshed):

    cd $ROOT
    ./start.sh --web      # browser mode — fastest, no compile (recommended first run)
    ./start.sh            # native Tauri desktop window (slower first launch:
                          #   compiles ~487 Rust crates, needs ~3 GB disk)

Re-run the environment check any time:
    python3 setup/check_env.py
EOF
fi
