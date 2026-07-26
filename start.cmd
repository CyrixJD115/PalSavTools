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
REM
REM If you JUST ran setup\windows.ps1 in this terminal, your shell may not have
REM picked up the newly-installed tools yet. We probe the standard install dirs
REM (%USERPROFILE%\.local\bin, %USERPROFILE%\.cargo\bin) as a fallback. If that
REM still fails, OPEN A NEW TERMINAL so your shell picks up the updated PATH.
title PalworldSaveTools Launcher
cd /d "%~dp0"

REM --- resolve uv: PATH first, then known install dirs --------------------
set "UV_BIN="
where uv >nul 2>&1 && set "UV_BIN=uv"

if not defined UV_BIN (
    if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV_BIN=%USERPROFILE%\.local\bin\uv.exe"
)
if not defined UV_BIN (
    if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "UV_BIN=%USERPROFILE%\.cargo\bin\uv.exe"
)

if defined UV_BIN (
    REM Make sure start.py can also see cargo.
    if exist "%USERPROFILE%\.cargo\bin\cargo.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    "%UV_BIN%" run python start.py %*
    goto :done
)

REM Fallback: a pre-existing .venv (e.g. created by an earlier run).
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start.py %*
    goto :done
)

echo.
echo uv was not found on PATH or in any standard install location.
echo.
echo You probably need to install it first -- run the one-time setup script:
echo     powershell -ExecutionPolicy Bypass -File setup\windows.ps1
echo.
echo Or install uv directly from https://docs.astral.sh/uv/getting-started/installation/
echo.
echo If you JUST ran setup\windows.ps1 in this terminal, close it and OPEN A NEW
echo TERMINAL before trying start.cmd again -- your shell needs to re-read its
echo PATH to see the tools that were installed.
echo.
pause
exit /b 1

:done
set "EXIT_CODE=%errorlevel%"
if %EXIT_CODE% neq 0 pause
exit /b %EXIT_CODE%
