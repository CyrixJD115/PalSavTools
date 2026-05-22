@echo off
cd /d "%~dp0\.."
.venv\Scripts\python.exe scripts\update_game_data.py
pause
