@echo off
setlocal enabledelayedexpansion
title StereoForge Launcher
cd /d "%~dp0"

echo ===================================================
echo   StereoForge: Stereoscopic 3D MVC Suite
echo   Imagined by writesimply.bcc * Coded by Gemini
echo ===================================================
echo.

:: 1. Locate Python
set "PYTHON=python"
python --version >nul 2>&1
if errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=py -3"
    ) else (
        for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
            if exist "%%D\python.exe" set "PYTHON=%%D\python.exe"
        )
    )
)

%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ was not found on your system.
    echo Please install Python from https://www.python.org/ or run:
    echo   winget install Python.Python.3.12
    echo and ensure "Add python.exe to PATH" is checked.
    echo.
    pause
    exit /b 1
)

:: 2. Auto-detect MKVToolNix
if exist "C:\Program Files\MKVToolNix" set "PATH=%PATH%;C:\Program Files\MKVToolNix"
if exist "C:\Program Files (x86)\MKVToolNix" set "PATH=%PATH%;C:\Program Files (x86)\MKVToolNix"
if exist "%LOCALAPPDATA%\Programs\MKVToolNix" set "PATH=%PATH%;%LOCALAPPDATA%\Programs\MKVToolNix"
if exist "%~dp0tools\MKVToolNix" set "PATH=%PATH%;%~dp0tools\MKVToolNix"
if exist "%~dp0tools" set "PATH=%PATH%;%~dp0tools"
if exist "%~dp0bin" set "PATH=%PATH%;%~dp0bin"

:: 3. Auto-detect tsMuxeR and subwoofa
if exist "%~dp0tools" set "PATH=%PATH%;%~dp0tools"
if exist "%~dp0tools\tsMuxeR" set "PATH=%PATH%;%~dp0tools\tsMuxeR"
if exist "C:\Program Files\tsMuxeR" set "PATH=%PATH%;C:\Program Files\tsMuxeR"
if exist "C:\Program Files (x86)\tsMuxeR" set "PATH=%PATH%;C:\Program Files (x86)\tsMuxeR"
if exist "C:\tsMuxeR" set "PATH=%PATH%;C:\tsMuxeR"
if exist "D:\tsMuxeR" set "PATH=%PATH%;D:\tsMuxeR"
if exist "F:\TSMuxer" set "PATH=%PATH%;F:\TSMuxer"
if exist "%LOCALAPPDATA%\Programs\tsMuxeR" set "PATH=%PATH%;%LOCALAPPDATA%\Programs\tsMuxeR"
if exist "%LOCALAPPDATA%\Subwoofa" set "PATH=%PATH%;%LOCALAPPDATA%\Subwoofa"

:: 4. Auto-detect FFmpeg
if exist "C:\ffmpeg\bin" set "PATH=%PATH%;C:\ffmpeg\bin"
if exist "C:\Program Files\ffmpeg\bin" set "PATH=%PATH%;C:\Program Files\ffmpeg\bin"
if exist "%LOCALAPPDATA%\Programs\ffmpeg\bin" set "PATH=%PATH%;%LOCALAPPDATA%\Programs\ffmpeg\bin"
if exist "%~dp0tools\ffmpeg\bin" set "PATH=%PATH%;%~dp0tools\ffmpeg\bin"

:: 5. Dependency presence check
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg was not detected in PATH or C:\ffmpeg\bin.
    echo   StereoForge requires FFmpeg. You can easily install it via PowerShell:
    echo     winget install Gyan.FFmpeg
    echo.
)

where mkvmerge >nul 2>&1
if errorlevel 1 (
    echo [NOTE] MKVToolNix - mkvmerge was not detected.
    echo   Needed for 3D MVC Matroska .mkv packaging. Install via:
    echo     winget install MKVToolNix.MKVToolNix
    echo.
)

:: 6. Python packages check
echo Checking Python dependencies...
%PYTHON% -c "import PySide6, numpy" >nul 2>&1
if errorlevel 1 (
    echo Dependencies not found. Installing from requirements.txt...
    %PYTHON% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
)

:: 6b. Bundled tools check (tsMuxeR and Subwoofa DTS-HD MA)
if not exist "%~dp0tools\tsMuxeR.exe" (
    echo Setting up bundled tools (tsMuxeR and Subwoofa)...
    %PYTHON% "%~dp0tools\download_tools.py"
) else if not exist "%~dp0tools\subwoofa-cli.exe" (
    echo Setting up bundled tools (Subwoofa DTS-HD MA)...
    %PYTHON% "%~dp0tools\download_tools.py"
)

:: 7. Launch StereoForge
echo Launching StereoForge GUI...
set "PYTHONPATH=%~dp0"
%PYTHON% -m stereoforge.ui.app
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with error.
    pause
)
