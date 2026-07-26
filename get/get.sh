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
    # NOTE: use printf with $'...' ANSI-C quoting, NOT a cat<<EOF heredoc.
    # Heredocs emit literal '\033' characters (no escape interpretation), which
    # shows up as raw "\033[1m..." garbage in the terminal.
    printf '\n\033[1m\033[96m\n'
    printf '  ___      _                _    _ ___              _____         _    \n'
    printf ' | _ \\__ _| |_ __ _____ _ _| |__| / __| __ ___ ____|_   _|__  ___| |___\n'
    printf " |  _/ _\` | \\ V  V / _ \\ '_| / _\` \\__ \\/ _\` \\ V / -_)| |/ _ \\/ _ \\(_-<\n"
    printf ' |_| \\__,_|_|\\_/\\_/\\___/_| |_\\__,_|___/\\__,_|\\_/\\___||_|\\___/\\___/_/__/\n'
    printf '\033[0m\n'
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
    # Announce the install destination loudly and FIRST, so there's no surprise
    # about where the project is going. The default is $PWD/PalSavTools — i.e.
    # whatever folder the terminal is in when the command runs.
    printf '\n\033[1mInstalling to:\033[0m \033[96m%s\033[0m\n' "$CLONE_DIR"
    if [[ "$CLONE_DIR" == "$PWD/PalSavTools" ]]; then
        c_hint "That's a new 'PalSavTools' folder inside your current directory ($PWD)."
        c_hint "To install somewhere else, cancel now and re-run with: --dest /your/path"
    fi
    c_step "1/3  Clone PalworldSaveTools"
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

# Tell the setup script it's being called by get.sh, so it skips its own
# final summary (get.sh prints the clearer one below).
export PST_GET_INVOKED=1

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
# NOTE: use printf with %s for the interpolated $CLONE_DIR, NOT a cat<<EOF
# heredoc. Heredocs emit literal '\033' (no escape interpretation), which shows
# up as raw "\033[1m..." garbage in the terminal.
local_bar=$'\033[1m\033[96m''═══════════════════════════════════════════════════════════'$'\033[0m'
printf '\n%s\n' "$local_bar"
printf '\033[1m  Setup complete — one step left to launch PST.\033[0m\n'
printf '%s\n\n' "$local_bar"
printf 'The project is installed at:\n'
printf '    \033[96m%s\033[0m\n\n' "$CLONE_DIR"
printf '\033[1m1. Open a NEW terminal\033[0m (so your shell picks up the tools we just installed).\n'
printf '\n'
printf '\033[1m2. Change into the project folder:\033[0m\n'
printf '    \033[96mcd %s\033[0m\n\n' "$CLONE_DIR"
printf '\033[1m3. Launch PST\033[0m — pick ONE of:\n\n'
printf '    \033[92m./start.sh --web\033[0m     browser mode  \033[2m(fastest — opens http://127.0.0.1:16920,\n'
printf '                                  no compile; recommended for your first run)\033[0m\n'
printf '    \033[92m./start.sh\033[0m            native window \033[2m(slower first launch: compiles ~487 Rust\n'
printf '                                  crates for the Tauri desktop window, needs ~3 GB disk)\033[0m\n\n'
printf '%s\n' "$local_bar"
printf '\033[2mTip: re-check the environment any time with:  python3 setup/check_env.py\033[0m\n'
printf '%s\n' "$local_bar"
