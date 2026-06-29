"""Nuitka build script for the PST WebUI backend (FastAPI sidecar).

Builds web/backend/main.py into a standalone executable that Tauri bundles
as a sidecar process. The binary auto-starts the FastAPI+uvicorn server.

Output goes to the Tauri binaries directory with the correct platform suffix
so `tauri build` picks it up for ``externalBin``.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
os.chdir(ROOT_DIR)

VENV_DIR = ".venv"
TAURI_BINARIES_DIR = os.path.join("web", "frontend", "src-tauri", "binaries")
MAIN_SCRIPT = os.path.join("web", "backend", "main.py")

_INCLUDE_PACKAGES = [
    # Web framework
    "fastapi",
    "uvicorn",
    "pydantic",
    "python_multipart",
    # PST engine (workspace packages)
    "palsav",
    "palooz",
    "coord",
    # Web backend itself
    "web",
    # Lazily imported src modules (runtime imports in tool_service)
    "palworld_aio",
    "resource_resolver",
    "palobject",
    # Serialization deps
    "orjson",
    "brotli",
    "cbor2",
    "zstandard",
    # Optional but used by palobject / importlib targets
    "msgpack",
    "packaging",
]

_EXCLUDE_PACKAGES = [
    "tkinter",
    "unittest",
    "pdb",
    "lib2to3",
    "distutils",
    "setuptools",
    "pip",
    "wheel",
    "venv",
    "ensurepip",
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "IPython",
    # No Qt in web mode
    "PySide6",
    "PyQt5",
    "PyQt6",
    "PySide2",
    # Build tools — not needed at runtime
    "nuitka",
    "cx_Freeze",
    # Old desktop-only deps
    "nerdfont",
    "py7zr",
]


def resolve_python():
    python_exe = (
        os.path.join(VENV_DIR, "Scripts", "python.exe")
        if sys.platform == "win32"
        else os.path.join(VENV_DIR, "bin", "python")
    )
    if os.path.exists(python_exe):
        return python_exe
    return "uv", "run", "python"


def check_nuitka(python_cmd):
    cmd = list(python_cmd) + ["-m", "nuitka", "--version"]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_platform_tag():
    mach = os.uname().machine if hasattr(os, "uname") else "x86_64"
    if sys.platform == "win32":
        return f"x86_64-pc-windows-msvc"
    elif sys.platform == "darwin":
        return f"{mach}-apple-darwin"
    else:
        return f"{mach}-unknown-linux-gnu"


def build_with_nuitka(onefile: bool = True):
    python_parts = resolve_python()
    python_cmd = list(python_parts) if isinstance(python_parts, (list, tuple)) else [python_parts]

    if not check_nuitka(python_cmd):
        print("Nuitka is not installed.")
        print("Install it with: uv pip install nuitka")
        return 1

    print("Building PST WebUI backend with Nuitka...")

    cmd = python_cmd + ["-m", "nuitka"]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--standalone")

    cmd.append("--prefer-source-code")
    cmd.append("--assume-yes-for-downloads")

    # Whole src/ tree — needed for importlib-based module loading at runtime
    # (map_data_service, coord, container_ownership, palobject, etc.).
    # Also includes resources (game data, i18n, assets) and configs (runtime.cfg).
    cmd.append("--include-data-dir=src=src")
    # Built frontend SPA (so backend can serve it)
    frontend_build = os.path.join(ROOT_DIR, "web", "frontend", "build")
    if os.path.isdir(frontend_build):
        cmd.append("--include-data-dir=web/frontend/build=web/frontend/build")

    for pkg in _INCLUDE_PACKAGES:
        cmd.append(f"--include-package={pkg}")

    for pkg in _EXCLUDE_PACKAGES:
        cmd.append(f"--nofollow-import-to={pkg}")

    # Output to the Tauri binaries directory
    os.makedirs(TAURI_BINARIES_DIR, exist_ok=True)
    cmd.append(f"--output-dir={TAURI_BINARIES_DIR}")

    # Platform-specific naming for Tauri sidecar
    platform_tag = get_platform_tag()
    ext = ".exe" if sys.platform == "win32" else ""
    output_name = f"pst-backend-{platform_tag}{ext}"
    cmd.append(f"--output-filename={output_name}")

    # Ensure onefile doesn't create a nested subdir
    if onefile:
        # Nuitka onefile puts the binary at output-dir/output-filename
        pass

    cmd.append(MAIN_SCRIPT)

    print(f"Command: {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([
        os.path.join(ROOT_DIR, "src"),
        os.path.join(ROOT_DIR, "web"),
        env.get("PYTHONPATH", ""),
    ])
    result = subprocess.run(cmd, env=env)

    if result.returncode == 0:
        binary_path = os.path.join(TAURI_BINARIES_DIR, output_name)
        if os.path.exists(binary_path):
            size_mb = os.path.getsize(binary_path) / (1024 * 1024)
            print(f"Sidecar binary built: {binary_path} ({size_mb:.1f} MB)")
        else:
            print(f"Build complete — binary expected at {binary_path}")

    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Build PST WebUI backend as Nuitka sidecar")
    parser.add_argument("--onefile", action="store_true", default=True, help="Build single-file executable (default)")
    parser.add_argument("--onedir", action="store_true", help="Build directory distribution")
    args = parser.parse_args()

    onefile = args.onefile and not args.onedir
    return build_with_nuitka(onefile)


if __name__ == "__main__":
    sys.exit(main())
