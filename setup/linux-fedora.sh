#!/usr/bin/env bash
# PalworldSaveTools — Fedora / RHEL-family setup (dnf).
#   Targets: Fedora 39+, Rocky/Alma 9+ (with EPEL for some -devel packages).
#
# Installs every system dependency needed to *build and launch* PST from source:
# Python, Rust (cargo), Node.js, uv, plus the GTK/WebKit dev headers Tauri
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

c_step "1/5  dnf system packages"
sudo dnf install -y \
    gcc-c++ \
    make \
    pkgconf-pkg-config \
    git \
    curl \
    wget \
    file \
    python3 \
    python3-devel \
    python3-virtualenv \
    openssl-devel \
    glib2-devel \
    gtk3-devel \
    webkit2gtk4.1-devel \
    libappindicator-gtk3-devel \
    librsvg2-devel \
    patchelf
c_ok "system packages installed"

c_step "2/5  Rust toolchain (cargo)"
if have cargo; then
    c_ok "cargo already present ($(cargo --version))"
else
    c_info "installing rustup via dnf (or rustup.rs)"
    if sudo dnf install -y rustup; then
        rustup default stable
    else
        c_warn "rustup not packaged — falling back to rustup.rs"
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
            | sh -s -- -y --profile minimal
    fi
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
    have cargo && c_ok "cargo installed" || c_warn "cargo install failed"
fi

c_step "3/5  Node.js LTS + npm"
if have node && have npm; then
    c_ok "node already present ($(node --version))"
else
    # Fedora's nodejs is recent enough for our needs (≥ 18).
    sudo dnf install -y nodejs npm
    have node && c_ok "node installed ($(node --version))" || c_warn "node install failed"
fi

c_step "4/5  uv (Python package manager)"
if have uv; then
    c_ok "uv already present ($(uv --version))"
else
    c_info "installing uv from astral.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh
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
