#!/usr/bin/env python3
"""PalworldSaveTools — non-interactive, platform-aware build orchestrator.

Runs the build(s) valid for the *current* host with no menu. Pick stages with
flags; with no flags it builds everything it can for this platform.

Stages
------
  embed   Rust + embedded-CPython proof-of-concept binary
          (build/embed_python/, fetched python-build-standalone runtime)
  tauri   Tauri desktop app — frontend (npm) + npx tauri build
          (delegates to build/tauri/build_tauri.py)

Usage
-----
  python build/build.py                # build every stage valid on this host
  python build/build.py --embed        # only the embedded-CPython binary
  python build/build.py --tauri        # only the Tauri app
  python build/build.py --clean        # cargo clean + rm frontend build/ before building
  python build/build.py --embed --clean

Each stage is independent: a missing optional tool (npm, cargo) skips that
stage with a clear message rather than failing the run — unless it was the
*only* stage requested.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD = PROJECT_ROOT / 'build'
EMBED_CRATE = BUILD / 'embed_python'
EMBED_PYTHON = EMBED_CRATE / 'python'           # python-build-standalone tree
TAURI_SCRIPT = BUILD / 'tauri' / 'build_tauri.py'
FRONTEND_DIR = PROJECT_ROOT / 'app' / 'frontend'

_COLORS = (
    hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    and os.environ.get('TERM') not in ('dumb', '')
)


def _c(codes: str, s: str) -> str:
    return f'{codes}{s}\033[0m' if _COLORS else s


GREEN = lambda s: _c('\033[92m', s)
RED = lambda s: _c('\033[91m', s)
YELLOW = lambda s: _c('\033[93m', s)
BLUE = lambda s: _c('\033[94m', s)
CYAN = lambda s: _c('\033[96m', s)
BOLD = lambda s: _c('\033[1m', s)
DIM = lambda s: _c('\033[2m', s)


# --------------------------------------------------------------------------- #
# Host detection
# --------------------------------------------------------------------------- #
def detect_host() -> dict:
    """Single source of truth for platform/arch/Python-env specifics."""
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    # Normalize arch names to the triples PBS / rust use.
    arch = {'x86_64': 'x86_64', 'amd64': 'x86_64',
            'arm64': 'aarch64', 'aarch64': 'aarch64'}.get(machine, machine)

    if sysname.startswith('win') or os.name == 'nt':
        triple = f'{arch}-pc-windows-msvc'
        kind = 'win'
    elif sysname == 'darwin':
        triple = f'{arch}-apple-darwin'
        kind = 'mac'
    else:
        triple = f'{arch}-unknown-linux-gnu'
        kind = 'linux'

    # env var + rpath language the embedded interpreter needs per OS.
    if kind == 'win':
        lib_env, lib_dir = 'PATH', 'python/Library/bin'
    elif kind == 'mac':
        # PBS ships libpython under python/lib on macOS too.
        lib_env, lib_dir = 'DYLD_LIBRARY_PATH', 'python/lib'
    else:
        lib_env, lib_dir = 'LD_LIBRARY_PATH', 'python/lib'

    return {
        'kind': kind, 'arch': arch, 'triple': triple,
        'lib_env': lib_env, 'lib_dir': lib_dir,
    }


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None,
         label: str = '') -> int:
    print(f'\n  {BOLD("─" * 60)}')
    if label:
        print(f'  {BLUE(BOLD(label))}')
    shown = " ".join(cmd[:8]) + (" …" if len(cmd) > 8 else "")
    print(f'  {DIM("$ " + shown)}')
    print(f'  {BOLD("─" * 60)}\n')
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                        env=env).returncode
    mark = GREEN('PASS') if rc == 0 else RED('FAIL')
    print(f'\n  [{mark}]  {time.time() - t0:.1f}s  (exit {rc})\n')
    return rc


def _embed_env(host: dict) -> dict:
    """Env for the embedded-CPython build/run (rustc finds PBS via these)."""
    env = os.environ.copy()
    pbs_python = EMBED_PYTHON / 'bin' / ('python3' if host['kind'] != 'win'
                                         else 'python.exe')
    lib_abs = EMBED_CRATE / host['lib_dir']
    env['PYO3_PYTHON'] = str(pbs_python)
    env[host['lib_env']] = os.pathsep.join(
        [str(lib_abs), env.get(host['lib_env'], '')]
    )
    # Tell the rustc linker where libpython lives. PBS records prefix=/install,
    # which doesn't exist on the host, so we must point at the real lib dir.
    env['RUSTFLAGS'] = f'-L native={lib_abs}'
    env['PST_PYTHON_HOME'] = str(EMBED_PYTHON)
    return env


def fetch_pbs(host: dict) -> int:
    """Download python-build-standalone for this host triple if missing."""
    pbs_python = EMBED_PYTHON / 'bin' / ('python3' if host['kind'] != 'win'
                                         else 'python.exe')
    if pbs_python.exists():
        return 0
    print(f'  {DIM("python-build-standalone not present — fetching it")}')
    fetch = EMBED_CRATE / 'scripts' / 'fetch_pbs.sh'
    if not fetch.exists():
        print(f'  {RED("missing")} {fetch}')
        return 1
    # fetch_pbs.sh derives the host triple itself; --clean would re-fetch.
    return _run(['bash', str(fetch)], cwd=EMBED_CRATE,
                label=f'Fetch CPython runtime ({host["triple"]})')


def build_embed(host: dict, clean: bool) -> int:
    """Build + smoke-test the embedded Rust+CPython binary."""
    if not have('cargo'):
        print(f'  {YELLOW("skip embed:")} cargo not found on PATH')
        return -1                                   # -1 = skipped
    if (rc := fetch_pbs(host)) != 0:
        return rc
    if clean and (EMBED_CRATE / 'target').exists():
        shutil.rmtree(EMBED_CRATE / 'target')
    env = _embed_env(host)
    if (rc := _run(['cargo', 'build', '--release'], cwd=EMBED_CRATE, env=env,
                   label='Embed: Rust + embedded CPython (release)')) != 0:
        return rc
    # Smoke test the freshly built binary end-to-end.
    return _run(['./target/release/embed_python'], cwd=EMBED_CRATE, env=env,
                label='Embed: smoke test (add(10,20)=30)')


def build_tauri(host: dict, clean: bool) -> int:
    """Build the Tauri desktop app (frontend + native bundle)."""
    if not (have('npm') and have('npx')):
        print(f'  {YELLOW("skip tauri:")} npm/npx not found on PATH')
        return -1
    if not TAURI_SCRIPT.exists():
        print(f'  {YELLOW("skip tauri:")} {TAURI_SCRIPT} missing')
        return -1
    if clean and (FRONTEND_DIR / 'build').exists():
        shutil.rmtree(FRONTEND_DIR / 'build')
    py = sys.executable or 'python3'
    return _run([py, str(TAURI_SCRIPT)], cwd=PROJECT_ROOT,
                label=f'Tauri desktop app ({host["triple"]})')


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    args = sys.argv[1:]
    clean = '--clean' in args
    want_embed = '--embed' in args
    want_tauri = '--tauri' in args
    only = want_embed or want_tauri
    # No explicit target → build everything valid for this host.
    if not only:
        want_embed = want_tauri = True

    host = detect_host()
    print(f'\n  {CYAN(BOLD("PalworldSaveTools"))} — {BLUE("build")}  '
          f'{DIM(host["triple"])}'
          f'{("  --clean" if clean else "")}\n')

    results: list[tuple[str, int]] = []

    if want_embed:
        results.append(('embed', build_embed(host, clean)))
    if want_tauri:
        results.append(('tauri', build_tauri(host, clean)))

    print(f'\n  {BOLD("─" * 60)}')
    print(f'  {BOLD("Summary")}')
    overall = 0
    for name, rc in results:
        if rc == -1:
            tag = f'{YELLOW("SKIP")}'
        elif rc == 0:
            tag = f'{GREEN("PASS")}'
        else:
            tag = f'{RED("FAIL")}'
            overall = rc
        print(f'    {name:<8} {tag}')
    print()
    return overall


if __name__ == '__main__':
    sys.exit(main())
