#!/usr/bin/env bash
# StereoForge macOS Standalone Packaging Script
# Creates a portable zip archive for macOS (Apple Silicon M-series & Intel x86_64)

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
STAGE_DIR="$DIST_DIR/StereoForge_macOS"
ZIP_NAME="StereoForge_macOS.zip"

echo "=========================================================="
echo "📦 Packaging StereoForge for macOS..."
echo "=========================================================="

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
mkdir -p "$STAGE_DIR/tools"

# Copy python package
cp -R "$REPO_ROOT/stereoforge" "$STAGE_DIR/"
find "$STAGE_DIR/stereoforge" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Copy launchers and requirements
cp "$REPO_ROOT/run_stereoforge.sh" "$STAGE_DIR/"
chmod +x "$STAGE_DIR/run_stereoforge.sh"
cp "$REPO_ROOT/requirements.txt" "$STAGE_DIR/"
cp "$REPO_ROOT/README.md" "$STAGE_DIR/"
cp "$REPO_ROOT/STEREOFORGE_SPECIFICATION.md" "$STAGE_DIR/"

# Create macOS Quick Start Guide
cat << 'EOF' > "$STAGE_DIR/README_MACOS.txt"
StereoForge (macOS Edition)
===========================
Universal Stereoscopic 3D MVC Encoder & Disc Packaging Suite
Imagined by writesimply.bcc • Coded by Gemini • Audio by Subwoofa

QUICK START:
1. Open Terminal and navigate to this folder:
   cd /path/to/StereoForge_macOS
2. Make the launcher executable (if needed) and run:
   chmod +x run_stereoforge.sh && ./run_stereoforge.sh

SYSTEM REQUIREMENTS:
- macOS 12 (Monterey) or later (Apple Silicon M1/M2/M3/M4 or Intel Core)
- Python 3.10+ (brew install python)
- FFmpeg (brew install ffmpeg)
- MKVToolNix (brew install mkvtoolnix)

HARDWARE ACCELERATION:
- Pass 1 Base View uses Apple VideoToolbox (h264_videotoolbox) with hardware M-series Media Engines.
- Pass 2 MVC Dependent View utilizes multi-core CPU with ARM64 NEON / AVX2 vectorization.
EOF

# Compress into zip
echo "Creating $ZIP_NAME..."
cd "$DIST_DIR"
rm -f "$ZIP_NAME"
if command -v zip >/dev/null 2>&1; then
    zip -rq "$ZIP_NAME" "StereoForge_macOS"
else
    tar -a -c -f "$ZIP_NAME" "StereoForge_macOS"
fi

echo "🎉 macOS package created successfully at: $DIST_DIR/$ZIP_NAME"
