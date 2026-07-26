#!/usr/bin/env bash
# PalworldSaveTools — Fedora / RHEL-family setup (dnf).
#   Targets: Fedora 39+, Rocky/Alma 9+ (with EPEL for some -devel packages).
#
# Installs every system dependency needed to *build and launch* PST from source:
# Python, Rust (cargo), Node.js, uv, plus the GTK/WebKit dev headers Tauri
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

add_local_bin_to_path() {
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) export PATH="$HOME/.local/bin:$PATH" ;;
    esac
}

banner_new_terminal() {
    cat <<EOF

\033[1m\033[96m═══════════════════════════════════════════════════════════\033[0m
\033[1m  IMPORTANT: open a NEW terminal before running ./start.sh\033[0m
\033[2m  (so your shell picks up the tools we just installed)\033[0m
\033[1m\033[96m═══════════════════════════════════════════════════════════\033[0m
EOF
}

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
    c_info "installing Rust toolchain"
    # Fedora's `rustup` package ships ONLY `rustup-init`, not `rustup` — run
    # that to download the real toolchain. Fall back to rustup.rs if the
    # package is unavailable or the init fails.
    sudo dnf install -y rustup || true
    if have rustup-init; then
        rustup-init -y --profile minimal --default-toolchain stable
    elif ! have rustup; then
        c_info "dnf rustup unavailable — falling back to rustup.rs"
        if ! curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
                | sh -s -- -y --profile minimal --default-toolchain stable; then
            c_crit "rustup.rs installer failed"
            c_hint "Check your network, then re-run this script."
            exit 1
        fi
    fi
    [[ -r "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
    verify cargo "Rust install"
fi

c_step "3/5  Node.js LTS + npm"
if have node && have npm; then
    c_ok "node already present ($(node --version))"
else
    # Fedora's nodejs is recent enough for our needs (≥ 18).
    sudo dnf install -y nodejs npm
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
cat <<EOF

Done. From $ROOT, **in a new terminal**, launch PST with:
    ./start.sh            # native Tauri window
    ./start.sh --web      # browser mode (no native window)

Re-run the environment check any time:
    python3 setup/check_env.py
EOF
