#!/usr/bin/env bash
# PalworldSaveTools — Debian/Ubuntu setup (apt-based distros).
#   Targets: Ubuntu 24.04+, Linux Mint 22+, Debian 12+, Pop!_OS, etc.
#
# Installs every system dependency needed to *build and launch* PST from source:
# Python venv, Rust (cargo), Node.js, uv, plus the GTK/WebKit dev headers Tauri
# needs on Linux. Safe to re-run — every step is idempotent.
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

c_ok()   { printf '\033[92m✓\033[0m %s\n' "$*"; }
c_warn() { printf '\033[93m⚠\033[0m %s\n' "$*"; }
c_info() { printf '\033[96m›\033[0m %s\n' "$*"; }
c_step() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

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
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --profile minimal
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
    have cargo && c_ok "cargo installed" || { c_warn "cargo install failed — see output"; }
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
    have node && c_ok "node installed ($(node --version))" || c_warn "node install failed"
fi

c_step "4/5  uv (Python package manager)"
if have uv; then
    c_ok "uv already present ($(uv --version))"
else
    c_info "installing uv from astral.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # uv installs to ~/.local/bin; make sure it's on PATH for this shell.
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) export PATH="$HOME/.local/bin:$PATH" ;;
    esac
    have uv && c_ok "uv installed ($(uv --version))" || c_warn "uv install failed — open a new terminal"
fi

c_step "5/5  Verify"
cd "$ROOT"
python3 "$HERE/check_env.py" --mode=launch || true

cat <<EOF

Done. From $ROOT, launch PST with:
    ./start.sh            # native Tauri window
    ./start.sh --web      # browser mode (no native window)

If check_env reported warnings, re-run it any time:
    python3 setup/check_env.py
EOF
