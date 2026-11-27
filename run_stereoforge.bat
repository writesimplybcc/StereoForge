@echo off
title StereoForge Launcher
cd /d "%~dp0"

echo ===================================================
echo   StereoForge: Stereoscopic 3D MVC Suite
echo   Imagined by writesimply.bcc * Coded by Gemini
echo ===================================================
echo.

set "PYTHON=python"
where %PYTHON% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.10+ and add it to your system PATH.
    pause
    exit /b 1
)

echo Checking dependencies...
"%PYTHON%" -c "import PySide6, numpy" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Dependencies not found. Installing from requirements.txt...
    "%PYTHON%" -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Launching StereoForge GUI...
set "PYTHONPATH=%~dp0"
"%PYTHON%" -m stereoforge.ui.app
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    pause
)

