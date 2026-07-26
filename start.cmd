@echo off
REM PalworldSaveTools launcher (Windows).
REM
REM Thin wrapper around start.py -- the real bootstrap (venv, submodules, port
REM freeing, preflight, frontend + backend + optional Tauri orchestration) lives
REM there. Pass --web for browser mode; pass --check to run only the preflight.
REM
REM   start.cmd            native Tauri window
REM   start.cmd --web      browser mode (no native window)
REM   start.cmd --check    run only the environment check
title PalworldSaveTools Launcher
cd /d "%~dp0"

where uv >nul 2>&1 && (
    uv run python start.py %*
    goto :done
)

REM Fallback: a pre-existing .venv (e.g. created by an earlier run).
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start.py %*
    goto :done
)

echo uv not found -- it's required to manage PST's Python environment.
echo.
echo Either install uv from https://docs.astral.sh/uv/getting-started/installation/
echo ...or run the one-time setup script first:
echo     powershell -ExecutionPolicy Bypass -File setup\windows.ps1
pause
exit /b 1

:done
set "EXIT_CODE=%errorlevel%"
if %EXIT_CODE% neq 0 pause
exit /b %EXIT_CODE%
