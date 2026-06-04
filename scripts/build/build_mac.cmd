@echo off
title PST Builder - macOS (x64 + ARM64)
for /f "delims=" %%I in ('wsl wslpath "%~dp0..\.."') do set "WSL_DIR=%%I"
wsl -d archlinux -e bash -c "cd '%WSL_DIR%' && uv run --no-project --python 3.12 python build/build.py mac %*" || (
    echo macOS x64 build failed!
    pause
    exit /b 1
)
wsl -d archlinux -e bash -c "cd '%WSL_DIR%' && uv run --no-project --python 3.12 python build/build.py mac-arm %*" || (
    echo macOS ARM64 build failed!
    pause
    exit /b 1
)
echo === Both macOS builds completed ===
timeout /t 2 >nul
exit /b 0
