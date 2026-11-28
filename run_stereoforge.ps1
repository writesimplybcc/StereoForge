# StereoForge PowerShell Launcher
# Imagined by writesimply.bcc • Coded by Gemini

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  StereoForge: Stereoscopic 3D MVC Suite" -ForegroundColor Cyan
Write-Host "  Imagined by writesimply.bcc • Coded by Gemini" -ForegroundColor Gray
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Locate Python
$PythonExe = "python"
if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    if (Get-Command "py" -ErrorAction SilentlyContinue) {
        $PythonExe = "py"
    } else {
        $found = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $PythonExe = $found.FullName
        }
    }
}

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue) -and -not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python 3.10+ was not found on your system." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/ or run: winget install Python.Python.3.12" -ForegroundColor Yellow
    pause
    exit 1
}

# 2. Auto-detect MKVToolNix (mkvmerge)
$mkvDirs = @(
    "C:\Program Files\MKVToolNix",
    "C:\Program Files (x86)\MKVToolNix",
    "$env:LOCALAPPDATA\Programs\MKVToolNix",
    "$ScriptDir\tools\MKVToolNix",
    "$ScriptDir\tools",
    "$ScriptDir\bin"
)
foreach ($dir in $mkvDirs) {
    if (Test-Path $dir) { $env:PATH += ";$dir" }
}

# 3. Auto-detect tsMuxeR
$tsDirs = @(
    "$ScriptDir\tools\tsMuxeR",
    "$ScriptDir\tools",
    "$ScriptDir\bin",
    "C:\Program Files\tsMuxeR",
    "C:\Program Files (x86)\tsMuxeR",
    "C:\tsMuxeR",
    "D:\tsMuxeR",
    "F:\TSMuxer",
    "$env:LOCALAPPDATA\Programs\tsMuxeR"
)
foreach ($dir in $tsDirs) {
    if (Test-Path $dir) { $env:PATH += ";$dir" }
}

# 4. Auto-detect FFmpeg
$ffDirs = @(
    "C:\ffmpeg\bin",
    "C:\Program Files\ffmpeg\bin",
    "$env:LOCALAPPDATA\Programs\ffmpeg\bin",
    "$ScriptDir\tools\ffmpeg\bin"
)
foreach ($dir in $ffDirs) {
    if (Test-Path $dir) { $env:PATH += ";$dir" }
}

# 5. Dependency check warnings
if (-not (Get-Command "ffmpeg" -ErrorAction SilentlyContinue)) {
    Write-Host "[WARNING] FFmpeg was not detected in PATH or standard directories." -ForegroundColor Yellow
    Write-Host "  Install via PowerShell: winget install Gyan.FFmpeg" -ForegroundColor Gray
}

if (-not (Get-Command "mkvmerge" -ErrorAction SilentlyContinue)) {
    Write-Host "[NOTE] MKVToolNix (mkvmerge) was not detected. Needed for 3D MKVs." -ForegroundColor Yellow
    Write-Host "  Install via PowerShell: winget install MKVToolNix.MKVToolNix" -ForegroundColor Gray
}

# 6. Python packages check
Write-Host "Checking Python dependencies..." -ForegroundColor Cyan
$Check = & $PythonExe -c "import PySide6, numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install dependencies." -ForegroundColor Red
        pause
        exit 1
    }
}

# 6b. Bundled tools check (tsMuxeR and Subwoofa DTS-HD MA)
if (-not (Test-Path "$ScriptDir\tools\tsMuxeR.exe") -or -not (Test-Path "$ScriptDir\tools\subwoofa-cli.exe")) {
    Write-Host "Setting up bundled tools (tsMuxeR and Subwoofa DTS-HD MA)..." -ForegroundColor Cyan
    & $PythonExe "$ScriptDir\tools\download_tools.py"
}

# 7. Launch StereoForge
Write-Host "Launching StereoForge GUI..." -ForegroundColor Green
$env:PYTHONPATH = $ScriptDir
& $PythonExe -m stereoforge.ui.app
