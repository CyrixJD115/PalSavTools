"""Nuitka build for the PST WebUI backend sidecar (Tauri externalBin)."""

import os
import sys
import subprocess
import shutil
import argparse
import platform

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
os.chdir(ROOT_DIR)

VENV_DIR = ".venv"
FRONTEND_DIR = os.path.join(ROOT_DIR, "app", "frontend")
TAURI_BINARIES_DIR = os.path.join(FRONTEND_DIR, "src-tauri", "binaries")
MAIN_SCRIPT = os.path.join(ROOT_DIR, "app", "backend", "main.py")

_INCLUDE_MODULES = [
    "app",
    "palsav", "palsav.core", "palsav.archive", "palsav.paltypes",
    "palsav.gvas", "palsav.json_tools", "palsav._cityhash",
    "palsav.compressor", "palsav.compressor.enums",
    "palsav.compressor.oozlib", "palsav.compressor.zlib",
    "palsav.commands", "palsav.commands.convert",
    "palsav.commands.backup", "palsav.commands.diag",
    "palsav.commands.resave_test", "palsav.commands.auto_update",
    "palsav.commands.roundtrip_validation",
    "palsav.rawdata",
    "palooz", "coord",
    "orjson", "brotli", "cbor2", "zstandard",
]

_EXCLUDE_MODULES = [
    "tkinter", "unittest", "pdb", "lib2to3", "distutils",
    "setuptools", "pip", "wheel", "venv", "ensurepip",
    "numpy", "pandas", "matplotlib", "scipy", "IPython",
    "PySide6",
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


def get_target_triple():
    machine = platform.machine().lower()
    if sys.platform == "win32":
        arch = "x86_64" if machine in ("amd64", "x86_64") else machine
        return f"{arch}-pc-windows-msvc"
    elif sys.platform == "darwin":
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"{arch}-apple-darwin"
    else:
        arch = "x86_64" if machine in ("x86_64", "amd64") else machine
        return f"{arch}-unknown-linux-gnu"


def build_with_nuitka(onefile=True):
    python_parts = resolve_python()
    if isinstance(python_parts, tuple):
        python_cmd = list(python_parts)
    elif isinstance(python_parts, str):
        python_cmd = [python_parts]
    else:
        python_cmd = list(python_parts)

    if not check_nuitka(python_cmd):
        print("Nuitka is not installed.")
        print("Install it with: uv pip install nuitka")
        return 1

    os.makedirs(TAURI_BINARIES_DIR, exist_ok=True)

    cmd = python_cmd + ["-m", "nuitka"]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--standalone")

    cmd.append("--prefer-source-code")

    cmd.extend([
        "--include-data-dir=resources=resources",
        "--include-data-dir=src/data=src/data",
        "--product-name=Palworld Save Tools - Web Backend",
        "--assume-yes-for-downloads",
    ])

    if sys.platform == "win32":
        cmd.append("--windows-console-mode=disable")
    else:
        cmd.append("--disable-console")

    for mod in _INCLUDE_MODULES:
        cmd.append(f"--include-module={mod}")

    for mod in _EXCLUDE_MODULES:
        cmd.append(f"--nofollow-import-to={mod}")

    ext = ".exe" if sys.platform == "win32" else ""
    target_triple = get_target_triple()
    output_name = f"pst-backend-{target_triple}{ext}"

    cmd.append(f"--output-filename={output_name}")
    cmd.append(f"--output-dir={TAURI_BINARIES_DIR}")
    cmd.append(MAIN_SCRIPT)

    print(f"Building backend sidecar: {output_name}")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([
        os.path.join(ROOT_DIR, "src"),
        os.path.join(ROOT_DIR, "resources"),
        os.path.join(ROOT_DIR, "app"),
        env.get("PYTHONPATH", ""),
    ])
    result = subprocess.run(cmd, env=env)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="PST WebUI Backend Builder (Nuitka)")
    parser.add_argument("--onefile", action="store_true", help="Build single-file executable")
    parser.add_argument("--onedir", action="store_true", help="Build directory distribution")
    args = parser.parse_args()

    onefile = args.onefile or not args.onedir
    rc = build_with_nuitka(onefile)

    if rc == 0:
        ext = ".exe" if sys.platform == "win32" else ""
        target_triple = get_target_triple()
        exe_name = f"pst-backend-{target_triple}{ext}"
        exe_path = os.path.join(TAURI_BINARIES_DIR, exe_name)
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\nBackend sidecar ready: {exe_path} ({size_mb:.1f} MB)")
        else:
            print("\nBackend sidecar built. Check binaries/ for output.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
