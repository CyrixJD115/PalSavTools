@echo off
title PST Builder - macOS (x64 + ARM64)
where uv >nul 2>&1 || (
    echo uv not found. Install from https://docs.astral.sh/uv/
    pause
    exit /b 1
)
echo.
echo === Building macOS x64 ===
python "%~dp0build.py" mac %*
if %errorlevel% neq 0 (
    echo macOS x64 build failed!
    pause
    exit /b %errorlevel%
)
echo.
echo === Building macOS ARM64 ===
python "%~dp0build.py" mac-arm %*
if %errorlevel% neq 0 (
    echo macOS ARM64 build failed!
    pause
    exit /b %errorlevel%
)
echo.
echo === Both macOS builds completed ===
pause
exit /b 0
