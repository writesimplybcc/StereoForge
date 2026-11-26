@echo off
title StereoForge Launcher
cd /d "%~dp0"

echo ===================================================
echo   StereoForge: Stereoscopic 3D MVC Suite
echo   Imagined by writesimply.bcc * Coded by Gemini
echo ===================================================
echo.
echo Launching StereoForge GUI...

set "PYTHON=C:\Users\writesimply\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PYTHON%" (
    set "PYTHON=python"
)

set "PYTHONPATH=%~dp0"
start "" "%PYTHON%" -m stereoforge.ui.app
