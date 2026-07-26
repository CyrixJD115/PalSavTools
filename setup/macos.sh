#!/usr/bin/env bash
# PalworldSaveTools — macOS setup (Homebrew).
#
# macOS needs almost no system libraries for the browser/launch path — the
# build-time GTK/WebKit deps are Linux-only (Tauri uses WebKit shipped with the
# OS on macOS). This script just makes sure the toolchain is present:
#   Xcode Command Line Tools, Homebrew, Node.js, Rust, uv.
#
# Safe to re-run — every step is idempotent and verifies the tool actually
# works before moving on.
# See setup/README.md for what each piece is for and troubleshooting.
set -euo pipefail

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

c_step "1/5  Xcode Command Line Tools"
if xcode-select -p >/dev/null 2>&1; then
    c_ok "already installed ($(xcode-select -p))"
else
    c_info "installing — a GUI prompt will appear"
    # xcode-select --install returns non-zero immediately after triggering the
    # GUI prompt, so don't treat that as failure. The user finishes in the GUI.
    xcode-select --install 2>/dev/null || true
    c_warn "If a GUI prompt appeared, finish it, then re-run this script."
    c_hint "(xcode-select --install triggers the installer and returns immediately)"
fi

c_step "2/5  Homebrew"
if have brew; then
    c_ok "brew already present ($(brew --version | head -1))"
else
    c_info "installing Homebrew from brew.sh"
    # Fetch the install script first so we can detect a download failure
    # (the old `bash -c "$(curl ...)"` silently succeeded with an empty
    # script if curl failed).
    HB_TMP="$(mktemp)"
    trap 'rm -f "$HB_TMP"' EXIT
    if ! curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$HB_TMP"; then
        c_crit "failed to download the Homebrew installer"
        c_hint "Check your network, then re-run this script."
        exit 1
    fi
    if ! bash "$HB_TMP"; then
        c_crit "Homebrew installer reported a failure"
        c_hint "See the output above; fix the issue and re-run this script."
        exit 1
    fi
    rm -f "$HB_TMP"; trap - EXIT
    # Homebrew on Apple Silicon installs to /opt/homebrew; on Intel, /usr/local.
    for bp in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [[ -x "$bp" ]]; then
            eval "$("$bp" shellenv)"
            break
        fi
    done
    verify brew "Homebrew install"
fi

c_step "3/5  Node.js LTS + npm"
if have node && have npm; then
    c_ok "node already present ($(node --version))"
else
    if ! brew install node; then
        c_crit "brew install node failed"
        c_hint "See the output above; fix the issue and re-run this script."
        exit 1
    fi
    verify node "Node.js install"
    verify npm "npm install"
fi

c_step "4/5  Rust toolchain (cargo) + uv"
if have cargo; then
    c_ok "cargo already present ($(cargo --version))"
else
    c_info "installing Rust toolchain"
    if ! brew install rustup-init || ! rustup-init -y --profile minimal; then
        c_info "brew rustup-init failed — trying rustup.rs"
        if ! curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
                | sh -s -- -y --profile minimal; then
            c_crit "rustup installer failed"
            c_hint "Check your network, then re-run this script."
            exit 1
        fi
    fi
    [[ -r "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
    verify cargo "Rust install"
fi

if have uv; then
    c_ok "uv already present ($(uv --version))"
else
    if ! brew install uv; then
        c_info "brew uv failed — trying astral.sh installer"
        if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
            c_crit "uv installer failed"
            c_hint "Check your network, then re-run this script."
            exit 1
        fi
    fi
    # uv's astral.sh fallback installs to ~/.local/bin — must add it to PATH
    # before verify, or a successful install would be reported as missing.
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
