@echo off
title PST Builder - All Targets
for /f "delims=" %%I in ('wsl wslpath "%~dp0..\.."') do set "WSL_DIR=%%I"
wsl -d archlinux -e bash -c "cd '%WSL_DIR%' && uv run --no-project --python 3.12 python build/build.py all %*"
if errorlevel 1 (
    pause
    exit /b 1
)
echo.
echo === Build completed successfully! ===
timeout /t 2 >nul
exit /b 0
