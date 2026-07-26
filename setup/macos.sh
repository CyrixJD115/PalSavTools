#!/usr/bin/env bash
# PalworldSaveTools — macOS setup (Homebrew).
#
# macOS needs almost no system libraries for the browser/launch path — the
# build-time GTK/WebKit deps are Linux-only (Tauri uses WebKit shipped with the
# OS on macOS). This script just makes sure the toolchain is present:
#   Xcode Command Line Tools, Homebrew, Node.js, Rust, uv.
#
# Safe to re-run — every step is idempotent.
# See setup/README.md for what each piece is for and troubleshooting.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

c_ok()   { printf '\033[92m✓\033[0m %s\n' "$*"; }
c_warn() { printf '\033[93m⚠\033[0m %s\n' "$*"; }
c_info() { printf '\033[96m›\033[0m %s\n' "$*"; }
c_step() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

c_step "1/5  Xcode Command Line Tools"
if xcode-select -p >/dev/null 2>&1; then
    c_ok "already installed ($(xcode-select -p))"
else
    c_info "installing — a GUI prompt will appear"
    xcode-select --install || c_warn "CLT install needs the GUI prompt; finish it and re-run"
    xcode-select -p >/dev/null 2>&1 && c_ok "installed" || c_warn "not yet installed"
fi

c_step "2/5  Homebrew"
if have brew; then
    c_ok "brew already present ($(brew --version | head -1))"
else
    c_info "installing Homebrew from brew.sh"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Homebrew on Apple Silicon installs to /opt/homebrew; on Intel, /usr/local.
    for bp in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        [[ -x "$bp" ]] && eval "$("$bp" shellenv)" && break
    done
    have brew && c_ok "brew installed" || c_warn "brew install failed — finish it and re-run"
fi

c_step "3/5  Node.js LTS + npm"
if have node && have npm; then
    c_ok "node already present ($(node --version))"
else
    brew install node
    have node && c_ok "node installed ($(node --version))" || c_warn "node install failed"
fi

c_step "4/5  Rust toolchain (cargo) + uv"
if have cargo; then
    c_ok "cargo already present ($(cargo --version))"
else
    c_info "installing rustup via brew (or rustup.rs)"
    brew install rustup-init && rustup-init -y --profile minimal || {
        c_warn "brew rustup-init failed — trying rustup.rs"
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
            | sh -s -- -y --profile minimal
    }
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
    have cargo && c_ok "cargo installed" || c_warn "cargo install failed"
fi

if have uv; then
    c_ok "uv already present ($(uv --version))"
else
    brew install uv
    have uv && c_ok "uv installed ($(uv --version))" || {
        c_info "brew uv failed — trying astral.sh installer"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        have uv && c_ok "uv installed ($(uv --version))" || c_warn "uv install failed"
    }
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
