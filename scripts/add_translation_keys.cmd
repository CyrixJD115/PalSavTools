@echo off
title Add Translation Keys
cd /d "%~dp0\.."
where uv >nul 2>&1 || (
    echo uv not found. Install from https://docs.astral.sh/uv/
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\scripts\add_translation_keys.py
pause
