#!/usr/bin/env bash
# StereoForge Linux Standalone Packaging Script
# Creates a portable tarball for Linux (Ubuntu / Debian / Fedora / Arch)

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
STAGE_DIR="$DIST_DIR/StereoForge_Linux_x86_64"
TAR_NAME="StereoForge_Linux_x86_64.tar.gz"

echo "=========================================================="
echo "📦 Packaging StereoForge for Linux..."
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

# Create Linux Quick Start Guide
cat << 'EOF' > "$STAGE_DIR/README_LINUX.txt"
StereoForge (Linux Edition)
===========================
Universal Stereoscopic 3D MVC Encoder & Disc Packaging Suite
Imagined by writesimply.bcc • Coded by Gemini • Audio by Subwoofa

QUICK START:
1. Open Terminal in this folder:
   cd /path/to/StereoForge_Linux_x86_64
2. Launch StereoForge:
   chmod +x run_stereoforge.sh && ./run_stereoforge.sh

SYSTEM REQUIREMENTS:
- Linux x86_64 or aarch64 (Ubuntu 22.04+, Fedora 38+, Arch, Debian 12+)
- Python 3.10+ (sudo apt install python3 python3-pip)
- FFmpeg (sudo apt install ffmpeg)
- MKVToolNix (sudo apt install mkvtoolnix)

HARDWARE ACCELERATION:
- Pass 1 Base View supports Nvidia NVENC, Intel QSV, and VA-API.
- Pass 2 MVC Dependent View utilizes multi-core CPU with AVX2/AVX-512 vectorization.
EOF

# Compress into tar.gz
echo "Creating $TAR_NAME..."
cd "$DIST_DIR"
rm -f "$TAR_NAME"
tar -czf "$TAR_NAME" "StereoForge_Linux_x86_64"

echo "🎉 Linux package created successfully at: $DIST_DIR/$TAR_NAME"
