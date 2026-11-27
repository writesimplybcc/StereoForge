#!/usr/bin/env bash
# StereoForge Unix Launcher (Linux & macOS)
# Imagined by writesimply.bcc • Coded by Gemini

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================================="
echo "  StereoForge: Stereoscopic 3D MVC Suite"
echo "  Imagined by writesimply.bcc • Coded by Gemini"
echo "==================================================="
echo ""

# 1. Locate Python 3
PYTHON=""
for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python 3.10+ was not found in your PATH."
    echo "  macOS: brew install python"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  Arch: sudo pacman -S python python-pip"
    exit 1
fi

# 2. Add local tools and Homebrew paths
for tool_dir in "/opt/homebrew/bin" "/usr/local/bin" "$SCRIPT_DIR/tools" "$SCRIPT_DIR/bin"; do
    if [ -d "$tool_dir" ]; then
        export PATH="$tool_dir:$PATH"
    fi
done

# 3. Check for FFmpeg & MKVToolNix
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[WARNING] FFmpeg was not detected in PATH."
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  Fedora: sudo dnf install ffmpeg"
    echo ""
fi

if ! command -v mkvmerge >/dev/null 2>&1; then
    echo "[NOTE] MKVToolNix (mkvmerge) was not detected. Needed for 3D MKVs."
    echo "  macOS: brew install mkvtoolnix"
    echo "  Ubuntu/Debian: sudo apt install mkvtoolnix"
    echo "  Fedora: sudo dnf install mkvtoolnix"
    echo ""
fi

# 4. Check & install Python dependencies
echo "Checking Python dependencies..."
if ! "$PYTHON" -c "import PySide6, numpy" >/dev/null 2>&1; then
    echo "Installing missing dependencies from requirements.txt..."
    "$PYTHON" -m pip install -r requirements.txt
fi

# 5. Launch StereoForge GUI
echo "Launching StereoForge GUI..."
export PYTHONPATH="$SCRIPT_DIR"
exec "$PYTHON" -m stereoforge.ui.app
