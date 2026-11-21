@echo off
setlocal
cd /d "%~dp0"
"runtime\python.exe" -B "app\launch.py"
if errorlevel 1 pause
