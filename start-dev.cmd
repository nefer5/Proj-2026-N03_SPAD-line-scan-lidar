@echo off
setlocal
cd /d "%~dp0"
title LiDAR Model - Development Server
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" run.py --reload --open --port 8001
) else (
    python run.py --reload --open --port 8001
)
if errorlevel 1 (
    echo.
    echo Startup failed. Check the error above.
    echo First use requires Python and dependencies: python -m pip install -e .
    pause
)
endlocal
