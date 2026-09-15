@echo off
cd /d "%~dp0"
python -m gomoku
if errorlevel 1 pause
