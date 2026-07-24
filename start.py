#!/usr/bin/env python3
"""Bootstrap launcher — delegates to src/main.py."""
import os, sys, subprocess, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parent
MAIN = str(ROOT / "src" / "main.py")
ARGS = [MAIN, *sys.argv[1:]]

try:
    if shutil.which("uv"):
        raise SystemExit(subprocess.call(["uv", "run", *ARGS]))
    vpy = ROOT / ".venv" / "bin" / "python3"
    if os.name == "nt":
        vpy = ROOT / ".venv" / "Scripts" / "python.exe"
    elif not vpy.exists():
        vpy = ROOT / ".venv" / "bin" / "python"
    raise SystemExit(subprocess.call([str(vpy), *ARGS]))
except (KeyboardInterrupt, SystemExit):
    sys.exit(0)
