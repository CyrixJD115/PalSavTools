#!/usr/bin/env bash
# PalworldSaveTools — Arch Linux / EndeavourOS / Manjaro setup (pacman).
#
# Installs every system dependency needed to *build and launch* PST from source:
# Python, Rust (cargo), Node.js, uv, plus the GTK/WebKit dev headers Tauri
# needs on Linux. Safe to re-run — every step is idempotent.
#
# uv has no official pacman package; it is installed via the official installer.
# rustup is preferred over the distro rust package so the toolchain stays
# self-managed (matches what Tauri's docs assume).
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

c_step "1/5  pacman system packages"
# base-devel is a group; install the whole group (gcc, make, pkgconf, …).
sudo pacman -Sy --needed --noconfirm \
    base-devel \
    pkgconf \
    git \
    curl \
    wget \
    file \
    python \
    python-pip \
    python-virtualenv \
    openssl \
    glib2 \
    gtk3 \
    webkit2gtk-4.1 \
    libayatana-appindicator \
    librsvg \
    patchelf
c_ok "system packages installed"

c_step "2/5  Rust toolchain (cargo)"
if have cargo; then
    c_ok "cargo already present ($(cargo --version))"
else
    c_info "installing Rust toolchain"
    # Arch's `rustup` package ships ONLY `rustup-init`, not `rustup` — run
    # that to download the real toolchain. Fall back to rustup.rs if the
    # package is unavailable or the init fails.
    sudo pacman -S --needed --noconfirm rustup
    if have rustup-init; then
        rustup-init -y --profile minimal --default-toolchain stable
    elif ! have rustup; then
        c_warn "pacman rustup unavailable — falling back to rustup.rs"
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
            | sh -s -- -y --profile minimal --default-toolchain stable
    fi
    # shellcheck disable=SC1091
    [[ -r "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
    have cargo && c_ok "cargo installed ($(cargo --version))" \
        || c_warn "cargo install failed — open a new terminal or run rustup-init manually"
fi

c_step "3/5  Node.js LTS + npm"
if have node && have npm; then
    c_ok "node already present ($(node --version))"
else
    sudo pacman -S --needed --noconfirm nodejs npm
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
