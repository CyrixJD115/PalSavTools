import os
import sys
import subprocess
import shutil
import re
import argparse
import configparser

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, '..'))
os.chdir(ROOT_DIR)

VENV_DIR = '.venv'
USE_EXISTING_VENV = False
BUILD_CFG_PATH = os.path.join('src', 'data', 'configs', 'runtime.cfg')
BUILD_CFG_DIR = os.path.join('src', 'data', 'configs')
SPEC_FILE = os.path.join('build_specs', 'pst.spec')


def create_venv():
    if not os.path.exists(VENV_DIR):
        print('Creating virtual environment with uv...')
        subprocess.check_call(['uv', 'venv', VENV_DIR])
    else:
        print('Virtual environment already exists.')


def install_deps():
    print('Installing dependencies with uv sync...')
    subprocess.check_call(['uv', 'sync', '--all-extras'])
    lockfile = 'uv.lock'
    if os.path.exists(lockfile):
        os.remove(lockfile)


def sync_version():
    common_file = os.path.join('src', 'common.py')
    pyproject_file = 'pyproject.toml'
    spec_file = SPEC_FILE
    version = '2.0.0'
    if os.path.exists(common_file):
        with open(common_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('APP_VERSION'):
                    version = (
                        line.split('=')[1].strip().strip('"').strip("'")
                    )
                    break
    updates = [
        (
            pyproject_file,
            r'version\s*=\s*["\'].*?["\']',
            f'version="{version}"',
        ),
        (
            common_file,
            r"BRANCH_VERSION\s*=\s*['\"].*?['\"]",
            "BRANCH_VERSION = 'main'",
        ),
    ]
    for file_path, pattern, replacement in updates:
        if not os.path.exists(file_path):
            continue
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(pattern, replacement, content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    print(f'Synchronized version to {version} and branch to main')


def build_with_pyinstaller():
    print('Running PyInstaller build...')
    python_exe = (
        os.path.join(VENV_DIR, 'Scripts', 'python.exe')
        if sys.platform == 'win32'
        else os.path.join(VENV_DIR, 'bin', 'python')
    )
    cmd = [python_exe, '-m', 'PyInstaller', SPEC_FILE, '--clean', '-y']
    if os.path.exists(python_exe):
        subprocess.check_call(cmd)
    else:
        subprocess.check_call(['uv', 'run'] + cmd)
    lockfile = 'uv.lock'
    if os.path.exists(lockfile):
        os.remove(lockfile)


def clean_build_artifacts():
    items = [
        'PalworldSaveTools.egg-info',
        'src/PalworldSaveTools.egg-info',
        'Backups',
        'build',
        'dist',
        'Logs',
    ]
    for item in items:
        if os.path.exists(item):
            print(f'Removing {item}...')
            if os.path.isdir(item):
                shutil.rmtree(item, ignore_errors=True)
            else:
                os.remove(item)
    for root, dirs, files in os.walk('.', topdown=False):
        for d in dirs:
            if d == '__pycache__':
                path = os.path.join(root, d)
                shutil.rmtree(path, ignore_errors=True)


def set_standalone_mode(enabled: bool):
    os.makedirs(BUILD_CFG_DIR, exist_ok=True)
    if not os.path.exists(BUILD_CFG_PATH):
        cfg = configparser.ConfigParser()
        cfg['build'] = {'standalone': 'false'}
        with open(BUILD_CFG_PATH, 'w', encoding='utf-8') as f:
            cfg.write(f)
    cfg = configparser.ConfigParser()
    cfg['build'] = {'standalone': 'true' if enabled else 'false'}
    with open(BUILD_CFG_PATH, 'w', encoding='utf-8') as f:
        cfg.write(f)
    mode = 'standalone' if enabled else 'source'
    print(f'Set build mode to: {mode}')


def get_app_version():
    common_file = os.path.join('src', 'common.py')
    if not os.path.exists(common_file):
        return 'unknown'
    with open(common_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('APP_VERSION'):
                return (
                    line.split('=')[1].strip().strip('"').strip("'")
                )
    return 'unknown'


def main():
    global USE_EXISTING_VENV
    parser = argparse.ArgumentParser(
        description='PalworldSaveTools Builder (PyInstaller)',
    )
    parser.add_argument(
        '--use-venv',
        action='store_true',
        help='Reuse existing venv, do not recreate it',
    )
    args = parser.parse_args()
    USE_EXISTING_VENV = args.use_venv
    clean_build_artifacts()
    if not USE_EXISTING_VENV:
        create_venv()
        install_deps()
    else:
        print('Using existing virtual environment...')
    sync_version()
    set_standalone_mode(True)
    try:
        build_with_pyinstaller()
    finally:
        set_standalone_mode(False)
    version = get_app_version()
    exe_name = 'PalworldSaveTools.exe' if sys.platform == 'win32' else 'PalworldSaveTools'
    exe_path = os.path.join('dist', exe_name)
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f'Build complete: {exe_path} ({size_mb:.1f} MB)')
    else:
        print('Build complete but executable not found in dist/')


if __name__ == '__main__':
    main()
