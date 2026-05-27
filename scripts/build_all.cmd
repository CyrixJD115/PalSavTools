@echo off
title PST Builder - All Targets
where uv >nul 2>&1 || (
    echo uv not found. Install from https://docs.astral.sh/uv/
    pause
    exit /b 1
)
python "%~dp0build.py" all %*
pause
exit /b %errorlevel%
