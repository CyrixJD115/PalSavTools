#!/usr/bin/env python3
"""Bootstrap launcher — delegates to src/main.py."""
import os, sys, subprocess, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
MAIN = ROOT / "src" / "main.py"

if not (ROOT / ".venv").exists():
    print("No .venv found — run `uv sync` or `uv venv` first.")
    sys.exit(1)

vpy = ROOT / ".venv" / "bin" / "python3"
if os.name == "nt":
    vpy = ROOT / ".venv" / "Scripts" / "python.exe"
elif not vpy.exists():
    vpy = ROOT / ".venv" / "bin" / "python"

sys.exit(subprocess.call([str(vpy), str(MAIN), *sys.argv[1:]]))
