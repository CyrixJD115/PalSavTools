from __future__ import annotations
import os, sys, subprocess, shutil, pathlib, argparse, threading, webbrowser, time, urllib.request, urllib.error
PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
uv_lock = PROJECT_DIR / 'uv.lock'
if uv_lock.exists():
    uv_lock.unlink()
VENV_DIR = PROJECT_DIR / '.venv'
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
LOGO = "\n  ___      _                _    _ ___              _____         _    \n | _ \\__ _| |_ __ _____ _ _| |__| / __| __ ___ ____|_   _|__  ___| |___\n |  _/ _` | \\ V  V / _ \\ '_| / _` \\__ \\/ _` \\ V / -_)| |/ _ \\/ _ \\(_-<\n |_| \\__,_|_|\\_/\\_/\\___/_| |_\\__,_|___/\\__,_|\\_/\\___||_|\\___/\\___/_/__/\n"
def log(msg: str, color: str=''):
    print(f'{color}{msg}{RESET}')
def venv_python() -> pathlib.Path:
    if os.name == 'nt':
        return VENV_DIR / 'Scripts' / 'python.exe'
    return VENV_DIR / 'bin' / 'python'
def ensure_venv():
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
    uv_lock = PROJECT_DIR / 'uv.lock'
    if uv_lock.exists():
        uv_lock.unlink()
    if result.returncode == 0:
        log('Environment ready', GREEN)
        return True
    else:
        log('Failed to install dependencies', RED)
        if VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        return False

FRONTEND_PORT = 16920
BACKEND_PORT = 16921

def free_ports():
    if os.name == 'nt':
        return
    for port in (FRONTEND_PORT, BACKEND_PORT):
        try:
            subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True, timeout=5)
        except (subprocess.CalledProcessError, OSError, FileNotFoundError):
            pass

def start_webui(vpy: pathlib.Path):
    """Start frontend dev server and backend, return (frontend_proc, backend_proc)."""
    frontend_dir = PROJECT_DIR / 'app' / 'frontend'
    backend_py = PROJECT_DIR / 'app' / 'backend' / 'main.py'

    _npm = shutil.which('npm')
    if not _npm:
        log('npm not found — install Node.js from https://nodejs.org', RED)
        sys.exit(1)

    nm = frontend_dir / 'node_modules'
    if not nm.exists() or not any(nm.iterdir()):
        log('Installing frontend dependencies...', CYAN)
        r = subprocess.run([_npm, 'install'], cwd=str(frontend_dir))
        if r.returncode != 0:
            log('Failed to install frontend dependencies', RED)
            sys.exit(1)

    frontend_proc = subprocess.Popen(
        [_npm, 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '16920'],
        cwd=str(frontend_dir),
        env={**os.environ, 'PST_BACKEND_URL': 'http://127.0.0.1:16921'},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        bufsize=1,
    )

    def log_frontend():
        out = frontend_proc.stdout
        if out:
            try:
                for line in iter(out.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        print(f'{DIM}[frontend] {stripped}{RESET}')
            except Exception:
                pass
    t = threading.Thread(target=log_frontend, daemon=True)
    t.start()

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
    t3 = threading.Thread(target=poll_frontend, daemon=True)
    t3.start()

    log('Starting PST WebUI backend...', GREEN)
    backend_proc = subprocess.Popen(
        [str(vpy), str(backend_py)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0,
    )

    def log_backend():
        out = backend_proc.stdout
        if out:
            try:
                for line in iter(out.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        print(f'{DIM}[backend] {stripped}{RESET}')
            except Exception:
                pass
    t2 = threading.Thread(target=log_backend, daemon=True)
    t2.start()

    log(f'  Frontend → http://127.0.0.1:16920', GREEN)
    log(f'  Backend  → http://127.0.0.1:16921', GREEN)

    return frontend_proc, backend_proc, frontend_ready

def cleanup_procs(*procs: subprocess.Popen):
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

def main():
    parser = argparse.ArgumentParser(description='PalworldSaveTools')
    parser.add_argument('--web', action='store_true', help='Launch WebUI in browser instead of native window')
    args = parser.parse_args()

    print(f'{BOLD}{LOGO}{RESET}')
    if not ensure_venv():
        log('Setup failed', RED)
        input('Press Enter to exit...')
        sys.exit(1)

    free_ports()
    vpy = venv_python()
    frontend_proc, backend_proc, frontend_ready = start_webui(vpy)

    if args.web:
        log(f'  Press Ctrl+C to stop', DIM)
        if frontend_ready.wait(timeout=60):
            url = 'http://127.0.0.1:16920'
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
            log(f'  Frontend server did not start within 60s', YELLOW)
            log(f'  Try opening {CYAN}http://127.0.0.1:16920{RESET}{YELLOW} manually{RESET}', YELLOW)

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
    else:
        log('Launching WebUI window...', GREEN)
        log(f'  Press Ctrl+C or close the window to stop', DIM)
        if frontend_ready.wait(timeout=60):
            npm = shutil.which('npm')
            if not npm:
                log('npm not found — cannot launch Tauri', RED)
                log(f'  Open {CYAN}http://127.0.0.1:16920{RESET}{YELLOW} manually instead{RESET}', YELLOW)
                frontend_proc.wait()
            else:
                tauri_dir = PROJECT_DIR / 'app' / 'frontend'
                log('  Attempting Tauri window...', DIM)
                tauri_proc = subprocess.Popen(
                    [npm, 'run', 'tauri', '--', 'dev'],
                    cwd=str(tauri_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                sidecar_missing = False
                def log_tauri():
                    nonlocal sidecar_missing
                    out = tauri_proc.stdout
                    if out:
                        try:
                            for line in iter(out.readline, ''):
                                stripped = line.rstrip()
                                if stripped:
                                    print(f'{DIM}[tauri] {stripped}{RESET}')
                                    if 'resource path' in stripped and 'doesn\'t exist' in stripped:
                                        sidecar_missing = True
                        except Exception:
                            pass
                t3 = threading.Thread(target=log_tauri, daemon=True)
                t3.start()

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

                if tauri_proc.returncode != 0 and sidecar_missing:
                    log('Tauri sidecar binary not found — falling back to browser mode.', YELLOW)
                    log(f'  Open {CYAN}http://127.0.0.1:16920{RESET}{YELLOW} in your browser{RESET}', YELLOW)
                    log(f'  Build the sidecar with: python build/tauri/build_tauri.py', DIM)
                    try:
                        frontend_proc.wait()
                    except KeyboardInterrupt:
                        pass
        else:
            log(f'  Frontend server did not start within 60s', YELLOW)
            log(f'  Try opening {CYAN}http://127.0.0.1:16920{RESET}{YELLOW} manually{RESET}', YELLOW)

        cleanup_procs(frontend_proc, backend_proc)

if __name__ == '__main__':
    main()
