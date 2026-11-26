@echo off
setlocal enabledelayedexpansion
title StereoForge Launcher
cd /d "%~dp0"

echo ===================================================
echo   StereoForge: Stereoscopic 3D MVC Suite
echo   Imagined by writesimply.bcc * Coded by Gemini
echo ===================================================
echo.

set "PYTHON=C:\Users\writesimply\AppData\Local\Programs\Python\Python312\python.exe"

if not exist "%PYTHON%" (
    set "PYTHON=python"
)

echo Checking dependencies...
"%PYTHON%" -c "import PySide6, numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing required packages: PySide6, numpy, opencv-python ...
    "%PYTHON%" -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Package installation failed. Please check your internet connection.
        pause
        exit /b 1
    )
)

echo Launching StereoForge GUI...
set "PYTHONPATH=%~dp0"
start "" "%PYTHON%" -m stereoforge.ui.app
