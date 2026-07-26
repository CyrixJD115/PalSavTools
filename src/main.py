"""Compatibility shim — delegates to the real launcher at ``start.py``.

The full bootstrap (venv, submodules, port freeing, preflight check, frontend
+ backend + optional Tauri orchestration) now lives in ``start.py`` at the
repo root. This file is kept so existing docs and muscle memory still work:

    uv run src/main.py --web

CI does not invoke this file, but users may. All args are forwarded.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

# Repo root = parent of this file's directory (src/).
START_PY = pathlib.Path(__file__).resolve().parent.parent / 'start.py'

if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, str(START_PY), *sys.argv[1:]]))
