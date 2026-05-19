@echo off
title PalworldSaveTools Auto-Update
setlocal enabledelayedexpansion
set "VENV_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "!VENV_PYTHON!" (
    echo .venv not found at !VENV_PYTHON!
    echo Run "uv sync" or "python -m venv .venv" first.
    pause
    exit /b 1
)
if "%~1"=="" (
    if exist "%~dp0Level.sav" (
        "!VENV_PYTHON!" "%~dp0auto_update.py" "%~dp0Level.sav"
    ) else (
        echo No Level.sav found in scripts folder. Drag a .sav file onto this .cmd.
        pause
        exit /b 1
    )
) else (
    "!VENV_PYTHON!" "%~dp0auto_update.py" %*
)
pause
exit /b %errorlevel%
