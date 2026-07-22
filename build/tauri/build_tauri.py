"""Tauri build orchestrator for PST WebUI.

Build pipeline:
1. Build the Svelte frontend (npm run build)
2. Build the Python backend into a sidecar binary (Nuitka)
3. Run `npx tauri build` to produce the final Tauri desktop app

Usage:
    python build/tauri/build_tauri.py              # full production build
    python build/tauri/build_tauri.py --skip-npm    # skip frontend build
    python build/tauri/build_tauri.py --skip-nuitka # skip backend build (use existing)
    python build/tauri/build_tauri.py --debug       # debug tauri build
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))

FRONTEND_DIR = os.path.join(ROOT_DIR, "app", "frontend")
TAURI_BINARIES_DIR = os.path.join(FRONTEND_DIR, "src-tauri", "binaries")
NUITKA_WEB_SCRIPT = os.path.join(ROOT_DIR, "build", "nuitka", "build_nuitka_web.py")


def banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def build_frontend():
    banner("Step 1/3: Building Svelte frontend")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
    )
    if result.returncode != 0:
        print("ERROR: Frontend build failed")
        return result.returncode
    print("Frontend build complete.")
    return 0


def build_backend():
    banner("Step 2/3: Building Python backend sidecar with Nuitka")
    result = subprocess.run(
        [sys.executable, NUITKA_WEB_SCRIPT, "--onefile"],
        cwd=ROOT_DIR,
    )
    if result.returncode != 0:
        print("ERROR: Backend (Nuitka) build failed")
        return result.returncode
    print("Backend sidecar build complete.")
    return 0


def build_tauri(debug: bool = False):
    banner("Step 3/3: Running tauri build")
    cmd = ["npx", "tauri", "build"]
    if debug:
        cmd.append("--debug")
    env = os.environ.copy()
    env.setdefault("APPIMAGE_EXTRACT_AND_RUN", "1")
    env.setdefault("STRIP", "/usr/bin/strip")
    result = subprocess.run(cmd, cwd=FRONTEND_DIR, env=env)
    if result.returncode != 0:
        print("ERROR: Tauri build failed")
        return result.returncode
    print("Tauri build complete!")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Build PST as a Tauri desktop app")
    parser.add_argument("--skip-npm", action="store_true", help="Skip frontend npm build")
    parser.add_argument("--skip-nuitka", action="store_true", help="Skip backend Nuitka build")
    parser.add_argument("--debug", action="store_true", help="Pass --debug to tauri build")
    parser.add_argument("--clean", action="store_true", help="Clean binaries dir before building")
    args = parser.parse_args()

    if args.clean and os.path.isdir(TAURI_BINARIES_DIR):
        shutil.rmtree(TAURI_BINARIES_DIR)
        print(f"Cleaned {TAURI_BINARIES_DIR}")

    if not args.skip_npm:
        if build_frontend() != 0:
            return 1
    else:
        print("Skipping frontend build (--skip-npm)")

    if not args.skip_nuitka:
        if build_backend() != 0:
            return 1
    else:
        print("Skipping backend build (--skip-nuitka)")

    if build_tauri(debug=args.debug) != 0:
        return 1

    print("\nDone! Tauri app built successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
