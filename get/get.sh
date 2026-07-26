#!/usr/bin/env bash
# PalworldSaveTools — one-shot installer for macOS / Linux.
#
# Clones the repo (with submodules), then runs the matching per-distro setup
# script to install all system dependencies (Rust, Node, uv, GTK/WebKit on
# Linux). Does NOT auto-launch — prints the exact command to run next.
#
# Usage (curl-pipe-bash):
#   curl -fsSL https://raw.githubusercontent.com/CyrixJD115/PalSavTools/master/get/get.sh | bash
#
# Or, with options:
#   curl -fsSL .../get/get.sh | bash -s -- --dest /path/to/clone --branch dev
#
# Options:
#   --dest <dir>     Where to clone (default: ./PalSavTools)
#   --branch <name>  Branch/tag to check out (default: master)
#   --repo <url>     Override the git remote (default: the public GitHub repo)
#   --no-clone       Skip cloning — assume CWD is already the repo root (run setup only)
#
# Safe to pipe to bash: set -euo pipefail, traps print a clear failure message,
# and a half-cloned dir is cleaned up on error.
set -euo pipefail

REPO_URL="https://github.com/CyrixJD115/PalSavTools.git"
BRANCH="master"
DEST=""
NO_CLONE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dest)    DEST="$2"; shift 2 ;;
        --branch)  BRANCH="$2"; shift 2 ;;
        --repo)    REPO_URL="$2"; shift 2 ;;
        --no-clone) NO_CLONE=1; shift ;;
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

[[ -z "$DEST" ]] && DEST="$PWD/PalSavTools"

# --- output helpers --------------------------------------------------------
c_ok()   { printf '\033[92m✓\033[0m %s\n' "$*"; }
c_info() { printf '\033[96m›\033[0m %s\n' "$*"; }
c_crit() { printf '\033[91m✗\033[0m %s\n' "$*"; }
c_hint() { printf '    \033[2m→ %s\033[0m\n' "$*"; }
c_step() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

banner() {
    cat <<EOF

\033[1m\033[96m
  ___      _                _    _ ___              _____         _
 | _ \\__ _| |_ __ _____ _ _| |__| / __| __ ___ ____|_   _|__  ___| |___
 |  _/ _\` | \\ V  V / _ \\ '_| / _\` \\__ \\/ _\` \\ V / -_)| |/ _ \\/ _ \\(_-<
 |_| \\__,_|_|\\_/\\_/\\___/_| |_\\__,_|___/\\__,_|\\_/\\___||_|\\___/\\___/_/__/
\033[0m
EOF
}

# Trap errors so the user sees a clear message instead of a bare exit code.
on_error() {
    local rc=$?
    echo ""
    c_crit "Install failed at step (exit $rc)."
    c_hint "Review the output above for the exact error."
    c_hint "If cloning failed, check your network or the --repo/--branch flags."
    c_hint "If a package install failed, re-run the matching setup/*.sh script directly."
    # Clean up a half-finished clone so a retry doesn't hit 'directory exists'.
    if [[ -n "${CLONE_DIR:-}" ]] && [[ "$NO_CLONE" -eq 0 ]] && [[ -d "$CLONE_DIR" ]]; then
        c_hint "Removing partial clone at $CLONE_DIR..."
        rm -rf "$CLONE_DIR"
    fi
    exit $rc
}
trap on_error ERR

banner

# --- step 1: clone ---------------------------------------------------------
if [[ "$NO_CLONE" -eq 1 ]]; then
    CLONE_DIR="$PWD"
    c_step "1/3  Using current directory (skipping clone)"
    c_ok "$CLONE_DIR"
else
    CLONE_DIR="$DEST"
    c_step "1/3  Clone PalSavTools"
    if ! command -v git >/dev/null 2>&1; then
        c_crit "git is required to clone the repo but isn't installed."
        c_hint "Install git first, then re-run this command."
        exit 1
    fi
    if [[ -d "$CLONE_DIR" ]]; then
        c_crit "Destination already exists: $CLONE_DIR"
        c_hint "Pick a different location with --dest <dir>, or remove the existing dir."
        exit 1
    fi
    c_info "git clone --recurse-submodules --branch $BRANCH $REPO_URL -> $CLONE_DIR"
    git clone --recurse-submodules --branch "$BRANCH" "$REPO_URL" "$CLONE_DIR"
    c_ok "cloned to $CLONE_DIR"
fi

# --- step 2: dispatch to the per-platform setup script ---------------------
c_step "2/3  Install system dependencies"
SETUP_DIR="$CLONE_DIR/setup"
if [[ ! -d "$SETUP_DIR" ]]; then
    c_crit "setup/ folder not found at $SETUP_DIR"
    c_hint "The clone may be incomplete or from a very old branch."
    exit 1
fi

case "$(uname -s)" in
    Darwin)
        c_info "macOS detected -> setup/macos.sh"
        bash "$SETUP_DIR/macos.sh"
        ;;
    Linux)
        c_info "Linux detected -> setup/linux.sh (auto-detects distro)"
        bash "$SETUP_DIR/linux.sh"
        ;;
    *)
        c_crit "Unsupported OS: $(uname -s)"
        c_hint "This installer supports macOS and Linux. Windows users: use get.ps1."
        exit 1
        ;;
esac

# --- step 3: next steps ----------------------------------------------------
c_step "3/3  Next steps"
cat <<EOF

\033[1mDone!\033[0m The project is set up at:

    $CLONE_DIR

\033[1m\033[96m═══════════════════════════════════════════════════════════\033[0m
\033[1m  IMPORTANT: open a NEW terminal, then run:\033[0m

    cd $CLONE_DIR
    ./start.sh            # native Tauri window
    ./start.sh --web      # browser mode (no native window)
\033[1m\033[96m═══════════════════════════════════════════════════════════\033[0m

A new terminal is needed so your shell picks up the tools we just installed.
EOF
