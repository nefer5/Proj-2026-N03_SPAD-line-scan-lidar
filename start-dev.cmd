@echo off
setlocal
cd /d "%~dp0"
title LiDAR Model - Development Server
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0run.py" --restart --reload --open
) else (
    python "%~dp0run.py" --restart --reload --open
)
if errorlevel 1 (
    echo.
    echo Startup failed. Check the error above.
    echo First use requires Python and dependencies: python -m pip install -e .
    pause
)
endlocal
