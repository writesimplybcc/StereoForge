# StereoForge PowerShell Launcher
# Imagined by writesimply.bcc • Coded by Gemini

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  StereoForge: Stereoscopic 3D MVC Suite" -ForegroundColor Cyan
Write-Host "  Imagined by writesimply.bcc • Coded by Gemini" -ForegroundColor Gray
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$PythonExe = "python"
if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    $PythonExe = "C:\Users\writesimply\AppData\Local\Programs\Python\Python312\python.exe"
}
if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue) -and -not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python was not found in your PATH." -ForegroundColor Red
    pause
    exit 1
}

if (Test-Path "C:\Program Files\MKVToolNix") {
    $env:PATH += ";C:\Program Files\MKVToolNix"
}
if (Test-Path "F:\TSMuxer") {
    $env:PATH += ";F:\TSMuxer"
}

Write-Host "Checking dependencies..." -ForegroundColor Yellow
$Check = & $PythonExe -c "import PySide6, numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies (PySide6, numpy, opencv-python)..." -ForegroundColor Yellow
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install dependencies." -ForegroundColor Red
        pause
        exit 1
    }
}

Write-Host "Launching StereoForge GUI..." -ForegroundColor Green
$env:PYTHONPATH = $ScriptDir
& $PythonExe -m stereoforge.ui.app
