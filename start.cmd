@echo off
title PalworldSaveTools Launcher
where uv >nul 2>&1 || (
echo uv not found. Install from https://docs.astral.sh/uv/
pause
exit /b 1
)
if exist "%~dp0.venv" rmdir /s /q "%~dp0.venv"
uv run "%~dp0start.py"
if exist "%~dp0uv.lock" del "%~dp0uv.lock"
pause
exit /b %errorlevel%