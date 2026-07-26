#!/usr/bin/env python3
"""PalworldSaveTools — single user-facing launcher.

This is the bootstrap that used to live in ``src/main.py``: it creates the
virtual environment, initializes submodules, frees the dev ports, runs a
preflight environment check, and orchestrates the frontend dev server +
backend (+ optional Tauri window) processes.

Usage
-----
    ./start.sh / start.cmd        → thin wrappers that exec this file
    uv run python start.py        → run directly
    python start.py --web         → browser mode (no native window)
    python start.py --check       → run only the preflight, then exit
    python start.py --skip-check  → boot without the preflight (advanced)

``src/main.py`` is kept as a tiny compatibility shim so existing docs and muscle
memory (``uv run src/main.py --web``) still work — it just delegates here.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

PROJECT_DIR = pathlib.Path(__file__).resolve().parent
SETUP_DIR = PROJECT_DIR / 'setup'
CHECK_ENV = SETUP_DIR / 'check_env.py'

# The old launcher removed uv.lock on every exit to keep runs reproducible.
# We keep that behavior but only unlink if present (no error if missing).
UV_LOCK = PROJECT_DIR / 'uv.lock'
VENV_DIR = PROJECT_DIR / '.venv'

FRONTEND_PORT = 16920
BACKEND_PORT = 16921

# --------------------------------------------------------------------------- #
# ANSI helpers
# --------------------------------------------------------------------------- #
USE_ANSI = True
if os.name == 'nt':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def ansi(code: str) -> str:
    return code if USE_ANSI else ''


RESET = ansi('\x1b[0m')
BOLD = ansi('\x1b[1m')
GREEN = ansi('\x1b[32m')
YELLOW = ansi('\x1b[33m')
RED = ansi('\x1b[31m')
CYAN = ansi('\x1b[36m')
DIM = ansi('\x1b[2m')

LOGO = (
    "\n  ___      _                _    _ ___              _____         _    \n"
    " | _ \\__ _| |_ __ _____ _ _| |__| / __| __ ___ ____|_   _|__  ___| |___\n"
    " |  _/ _` | \\ V  V / _ \\ '_| / _` \\__ \\/ _` \\ V / -_)| |/ _ \\/ _ \\(_-<\n"
    " |_| \\__,_|_|\\_/\\_/\\___/_| |_\\__,_|___/\\__,_|\\_/\\___||_|\\___/\\___/_/__/\n"
)


def log(msg: str, color: str = '') -> None:
    print(f'{color}{msg}{RESET}')


# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #
def run_preflight(mode: str) -> bool:
    """Run setup/check_env.py and return True if no critical issues were found.

    check_env.py is stdlib-only so it runs even before the venv exists. We
    invoke it with the *current* interpreter (uv run already gave us a good
    one) and surface its exit code.
    """
    if not CHECK_ENV.exists():
        log(f'  Preflight skipped — {CHECK_ENV} not found', YELLOW)
        return True
    log('Running environment preflight...', CYAN)
    # Inherit stdout/stderr so the colored report card streams through live.
    rc = subprocess.call([sys.executable, str(CHECK_ENV), '--mode', mode])
    if rc == 0:
        log('  Preflight passed', GREEN)
        return True
    log('  Preflight reported critical issues — fix them, then re-run.', RED)
    log(f'  (Tip: re-run {CYAN}python3 setup/check_env.py{RESET}'
        f'{RED} for details, or the setup script for your platform.)', RED)
    return False


# --------------------------------------------------------------------------- #
# venv
# --------------------------------------------------------------------------- #
def venv_python() -> pathlib.Path:
    if os.name == 'nt':
        return VENV_DIR / 'Scripts' / 'python.exe'
    return VENV_DIR / 'bin' / 'python'


def ensure_venv() -> bool:
    vpy = venv_python()
    if vpy.exists():
        return True
    log('Creating virtual environment...', CYAN)
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    result = subprocess.run(['uv', 'venv', str(VENV_DIR)])
    if result.returncode != 0:
        log('Failed to create venv', RED)
        return False
    log('Installing dependencies...', CYAN)
    result = subprocess.run(['uv', 'sync'])
    if UV_LOCK.exists():
        UV_LOCK.unlink()
    if result.returncode == 0:
        log('Environment ready', GREEN)
        return True
    log('Failed to install dependencies', RED)
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    return False


# --------------------------------------------------------------------------- #
# Submodules + ports + uesave prebuild
# --------------------------------------------------------------------------- #
def ensure_submodules() -> None:
    gitmodules = PROJECT_DIR / '.gitmodules'
    if not gitmodules.exists():
        return
    palsav_dir = PROJECT_DIR / 'src' / 'palsav-rs'
    if (palsav_dir / 'Cargo.toml').exists():
        return
    git = shutil.which('git')
    if not git:
        log('Git not found — cannot initialize submodules', YELLOW)
        log('  Run: git submodule update --init --recursive', YELLOW)
        return
    log('Initializing git submodules...', CYAN)
    r = subprocess.run([git, 'submodule', 'update', '--init', '--recursive'],
                       cwd=str(PROJECT_DIR))
    if r.returncode == 0:
        log('Submodules initialized', GREEN)
    else:
        log('Failed to initialize submodules', RED)


def free_ports() -> None:
    if os.name == 'nt':
        return
    for port in (FRONTEND_PORT, BACKEND_PORT):
        try:
            subprocess.run(['fuser', '-k', f'{port}/tcp'],
                           capture_output=True, timeout=5)
        except (subprocess.CalledProcessError, OSError, FileNotFoundError):
            pass


def _build_uesave() -> None:
    """Pre-build the Rust uesave binary in the background (best-effort)."""
    palsav_dir = PROJECT_DIR / 'src' / 'palsav-rs'
    if not (palsav_dir / 'Cargo.toml').exists():
        return
    suffix = '.exe' if os.name == 'nt' else ''
    binary = palsav_dir / 'target' / 'release' / f'uesave{suffix}'
    if binary.exists():
        return
    cargo = shutil.which('cargo')
    if not cargo:
        return
    log('Pre-building uesave (Rust save parser) in background…', DIM)
    subprocess.run(
        [cargo, 'build', '--release', '-p', 'uesave_cli'],
        cwd=str(palsav_dir), capture_output=True,
    )


# --------------------------------------------------------------------------- #
# WebUI orchestration
# --------------------------------------------------------------------------- #
def start_webui(vpy: pathlib.Path):
    """Start frontend dev server and backend; return (fe_proc, be_proc, ready)."""
    frontend_dir = PROJECT_DIR / 'app' / 'frontend'
    backend_py = PROJECT_DIR / 'app' / 'backend' / 'main.py'

    npm = shutil.which('npm')
    if not npm:
        log('npm not found — install Node.js from https://nodejs.org', RED)
        sys.exit(1)

    nm = frontend_dir / 'node_modules'
    if not nm.exists() or not any(nm.iterdir()):
        log('Installing frontend dependencies...', CYAN)
        r = subprocess.run([npm, 'install'], cwd=str(frontend_dir))
        if r.returncode != 0:
            log('Failed to install frontend dependencies', RED)
            sys.exit(1)

    frontend_proc = subprocess.Popen(
        [npm, 'run', 'dev', '--', '--host', '127.0.0.1',
         '--port', str(FRONTEND_PORT)],
        cwd=str(frontend_dir),
        env={**os.environ,
             'PST_BACKEND_URL': f'http://127.0.0.1:{BACKEND_PORT}'},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', bufsize=1,
    )

    def log_stream(proc, tag):
        out = proc.stdout
        if not out:
            return
        try:
            for line in iter(out.readline, ''):
                stripped = line.rstrip()
                if stripped:
                    print(f'{DIM}[{tag}] {stripped}{RESET}')
        except Exception:
            pass

    threading.Thread(target=log_stream, args=(frontend_proc, 'frontend'),
                     daemon=True).start()

    frontend_ready = threading.Event()
    FRONTEND_URL = f'http://127.0.0.1:{FRONTEND_PORT}'

    def poll_frontend():
        for _ in range(300):
            if frontend_proc.poll() is not None:
                return
            try:
                urllib.request.urlopen(FRONTEND_URL, timeout=1)
                frontend_ready.set()
                return
            except (urllib.error.URLError, OSError):
                time.sleep(1)

    threading.Thread(target=poll_frontend, daemon=True).start()

    log('Starting PST WebUI backend...', GREEN)
    backend_proc = subprocess.Popen(
        [str(vpy), str(backend_py)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=0,
    )
    threading.Thread(target=log_stream, args=(backend_proc, 'backend'),
                     daemon=True).start()

    log(f'  Frontend -> http://127.0.0.1:{FRONTEND_PORT}', GREEN)
    log(f'  Backend  -> http://127.0.0.1:{BACKEND_PORT}', GREEN)
    return frontend_proc, backend_proc, frontend_ready


def cleanup_procs(*procs: subprocess.Popen) -> None:
    for p in procs:
        if p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass


# --------------------------------------------------------------------------- #
# Tauri sidecar launcher (auto-created if missing) — moved verbatim from the
# old src/main.py; it's only reached in native (non --web) mode.
# --------------------------------------------------------------------------- #
def ensure_tauri_sidecar() -> pathlib.Path | None:
    tauri_dir = PROJECT_DIR / 'app' / 'frontend'
    binaries_dir = tauri_dir / 'src-tauri' / 'binaries'

    if binaries_dir.is_dir():
        for p in binaries_dir.iterdir():
            if p.name.startswith('pst-backend-') and p.is_file() \
                    and os.access(p, os.X_OK):
                return p

    log('  Sidecar missing — creating launcher script...', YELLOW)
    binaries_dir.mkdir(parents=True, exist_ok=True)
    import platform as _plat
    machine = _plat.machine().lower()
    arch = 'x86_64' if machine in ('x86_64', 'amd64') else machine
    if os.name == 'nt':
        triple = f'{arch}-pc-windows-msvc'
        script_path = binaries_dir / f'pst-backend-{triple}.cmd'
        script_path.write_text(
            f"@echo off\r\n"
            f"cd /d \"{PROJECT_DIR}\"\r\n"
            f"uv run python app/backend/main.py\r\n"
        )
    else:
        triple = f'{arch}-unknown-linux-gnu'
        script_path = binaries_dir / f'pst-backend-{triple}'
        script_path.write_text(
            "#!/bin/sh\n"
            'SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
            'PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"\n'
            'cd "$PROJECT_ROOT"\n'
            'exec uv run python app/backend/main.py\n'
        )
        script_path.chmod(0o755)
    log('  Launcher script created, starting Tauri...', GREEN)
    return script_path


def run_tauri(frontend_proc, backend_proc, frontend_ready) -> None:
    """Try to open a native Tauri window; fall back to browser mode on failure."""
    log('Launching WebUI window...', GREEN)
    log('  Press Ctrl+C or close the window to stop', DIM)
    if not frontend_ready.wait(timeout=60):
        log('  Frontend server did not start within 60s', YELLOW)
        log(f'  Try opening {CYAN}http://127.0.0.1:{FRONTEND_PORT}'
            f'{YELLOW} manually{RESET}', YELLOW)
        cleanup_procs(frontend_proc, backend_proc)
        return

    npm = shutil.which('npm')
    if not npm:
        log('npm not found — cannot launch Tauri', RED)
        log(f'  Open {CYAN}http://127.0.0.1:{FRONTEND_PORT}'
            f'{YELLOW} manually instead{RESET}', YELLOW)
        try:
            frontend_proc.wait()
        except KeyboardInterrupt:
            pass
        cleanup_procs(frontend_proc, backend_proc)
        return

    ensure_tauri_sidecar()
    tauri_dir = PROJECT_DIR / 'app' / 'frontend'

    log('  Attempting Tauri window...', DIM)
    tauri_proc = subprocess.Popen(
        [npm, 'run', 'tauri', '--', 'dev'],
        cwd=str(tauri_dir),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )

    def log_tauri():
        out = tauri_proc.stdout
        if not out:
            return
        try:
            for line in iter(out.readline, ''):
                stripped = line.rstrip()
                if stripped:
                    print(f'{DIM}[tauri] {stripped}{RESET}')
        except Exception:
            pass

    threading.Thread(target=log_tauri, daemon=True).start()

    try:
        tauri_proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        log('Tauri build still running — waiting indefinitely...', DIM)
        tauri_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if tauri_proc.poll() is None:
            cleanup_procs(tauri_proc)

    if tauri_proc.returncode != 0:
        log('Tauri window failed — falling back to browser mode.', YELLOW)
        log(f'  Open {CYAN}http://127.0.0.1:{FRONTEND_PORT}'
            f'{YELLOW} in your browser{RESET}', YELLOW)
        try:
            frontend_proc.wait()
        except KeyboardInterrupt:
            pass

    cleanup_procs(frontend_proc, backend_proc)


def run_browser(frontend_proc, backend_proc, frontend_ready) -> None:
    log('  Press Ctrl+C to stop', DIM)
    if frontend_ready.wait(timeout=60):
        url = f'http://127.0.0.1:{FRONTEND_PORT}'
        log(f'  Opening {url}...', DIM)
        try:
            if os.name == 'nt':
                subprocess.Popen(['explorer.exe', url])
            else:
                webbrowser.open(url)
        except Exception:
            log('  Unable to open browser automatically', YELLOW)
            log(f'  Open {CYAN}{url}{RESET}{YELLOW} manually{RESET}', YELLOW)
    else:
        log('  Frontend server did not start within 60s', YELLOW)
        log(f'  Try opening {CYAN}http://127.0.0.1:{FRONTEND_PORT}'
            f'{YELLOW} manually{RESET}', YELLOW)

    try:
        frontend_proc.wait()
        backend_proc.terminate()
        backend_proc.wait()
    except KeyboardInterrupt:
        cleanup_procs(frontend_proc, backend_proc)
        sys.exit(0)
    except Exception:
        cleanup_procs(frontend_proc, backend_proc)
        sys.exit(1)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description='PalworldSaveTools launcher')
    parser.add_argument('--web', action='store_true',
                        help='Launch in browser mode instead of a native window')
    parser.add_argument('--check', action='store_true',
                        help='Run only the preflight environment check, then exit')
    parser.add_argument('--skip-check', action='store_true',
                        help='Skip the preflight check (advanced)')
    args = parser.parse_args()

    print(f'{BOLD}{LOGO}{RESET}')

    # --check is a pure preflight run — no venv, no servers.
    if args.check:
        mode = 'tauri' if not args.web else 'launch'
        sys.stdout.flush()
        rc = subprocess.call(
            [sys.executable, str(CHECK_ENV), '--mode', mode])
        sys.exit(0 if rc == 0 else 1)

    # Preflight — soft mode: warnings don't abort, criticals do.
    if not args.skip_check:
        mode = 'launch' if args.web else 'tauri'
        sys.stdout.flush()
        if not run_preflight(mode):
            try:
                input('Press Enter to exit...')
            except EOFError:
                pass
            sys.exit(1)

    if not ensure_venv():
        log('Setup failed', RED)
        try:
            input('Press Enter to exit...')
        except EOFError:
            pass
        sys.exit(1)

    ensure_submodules()
    free_ports()
    vpy = venv_python()
    frontend_proc, backend_proc, frontend_ready = start_webui(vpy)

    # Pre-build the Rust save parser in the background while the UI starts.
    threading.Thread(target=_build_uesave, daemon=True).start()

    if args.web:
        run_browser(frontend_proc, backend_proc, frontend_ready)
    else:
        run_tauri(frontend_proc, backend_proc, frontend_ready)


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        # Keep the uv.lock cleanup consistent on any exit path.
        if UV_LOCK.exists():
            try:
                UV_LOCK.unlink()
            except OSError:
                pass
        sys.exit(0)
