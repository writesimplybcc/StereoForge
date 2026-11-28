# StereoForge
> **Imagined by writesimply.bcc • Coded by Gemini • Audio by Subwoofa**

---

StereoForge is an open-source, high-performance stereoscopic 3D video encoder and packaging suite. It replaces legacy, discontinued tools (such as FRIM) with a modern hybrid GPU + multi-core CPU architecture.

StereoForge converts 3D videos (Side-by-Side, Top-and-Bottom, dual-camera files, or legacy 2000s 3D camcorder footage) into:
1. **3D MVC Matroska (.mkv)** (for Meta Quest, Apple Vision Pro, Bigscreen VR, Skybox, 4XVR, and VLC).
2. **3D Blu-ray ISOs / BDMV** (for home theater 3D projectors and physical discs via tsMuxeR).

---

## Quick Start (Clean Install)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/writesimplybcc/StereoForge.git
   cd StereoForge
   ```

2. **Launch StereoForge:**
   * **Windows (x64 / ARM64):** Double-click **`run_stereoforge.bat`** (or run `.\run_stereoforge.ps1` in PowerShell).
   * **macOS (Apple Silicon & Intel) / Linux:** Run `chmod +x run_stereoforge.sh && ./run_stereoforge.sh` in Terminal.
   * The launcher automatically locates Python, installs missing Python dependencies from `requirements.txt`, auto-detects FFmpeg/MKVToolNix/tsMuxeR, and opens the GUI.

---

## Cross-Platform Compatibility Matrix

StereoForge is built on pure Python + Qt 6 (PySide6) and standard multimedia backends, providing first-class cross-platform support:

| Operating System | Architecture | Pass 1 Hardware Acceleration | Pass 2 CPU MVC Engine | Launcher |
| :--- | :--- | :--- | :--- | :--- |
| **Windows 10 / 11** | `x86_64` | Nvidia NVENC, Intel QSV, AMD AMF | Multi-core x264 (AVX2 / AVX-512) | `run_stereoforge.bat` |
| **Windows 11 on ARM** | `arm64` (Snapdragon X Elite) | Windows Media Foundation (`h264_mf`) / CPU | Multi-core x264 (ARM NEON) | `run_stereoforge.bat` |
| **macOS (Apple Silicon)** | `arm64` (M1, M2, M3, M4) | Apple VideoToolbox (`h264_videotoolbox`) | Multi-core x264 (ARM NEON) | `run_stereoforge.sh` |
| **macOS (Intel)** | `x86_64` | Apple VideoToolbox / Intel QSV | Multi-core x264 (AVX2) | `run_stereoforge.sh` |
| **Linux (Ubuntu/Fedora/Arch)** | `x86_64` & `aarch64` | Nvidia NVENC, Intel QSV, VAAPI | Multi-core x264 (AVX2 / NEON) | `run_stereoforge.sh` |

---

## Prerequisites & External Tools

StereoForge relies on standard tools for hardware encoding, container packaging, and disc authoring:

| Tool | Windows (PowerShell) | macOS (Homebrew) | Linux (Ubuntu / Debian) |
| :--- | :--- | :--- | :--- |
| **Python 3.10+** | `winget install Python.Python.3.12` | `brew install python` | `sudo apt install python3 python3-pip` |
| **FFmpeg** | `winget install Gyan.FFmpeg` | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| **MKVToolNix** | `winget install MKVToolNix.MKVToolNix` | `brew install mkvtoolnix` | `sudo apt install mkvtoolnix` |
| **tsMuxeR** *(Required for 3D Blu-ray ISO)* | Auto-installed or drop in `tools/` | Download macOS build / drop in `tools/` | Download Linux build / drop in `tools/` |
| **Subwoofa** *(Lossless DTS-HD MA Engine)* | Pre-bundled & auto-installed into `tools/` | Build from source / drop in `tools/` | Build from source / drop in `tools/` |

> **Note on Tool Discovery:** StereoForge automatically scans standard directories across all operating systems (including `C:\Program Files\MKVToolNix`, `C:\ffmpeg\bin`, `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`, `StereoForge/tools/`, and system `PATH`). You do not need to manually configure environment variables if tools are installed in their standard locations.

---

## Key Features

- **Hybrid Architecture & True MVC Compression:**
  - **Pass 1 (GPU Hardware):** Left Eye encoded with ultra-fast hardware acceleration (Nvidia NVENC, Intel QSV, AMD AMF, Apple VideoToolbox), generating a synchronized frame manifest.
  - **Pass 2 (Native C `stereoforge-core` - Default):** Right Eye uses **True MVC Inter-View Reference Injection** to predict macroblocks directly from the reconstructed Left Eye in `RefPicList0`, achieving **20–35% file size savings** while maintaining 1080p resolution per eye.
  - **GPU Hardware Turbo Option:** High-speed simulcast mode (60–100+ FPS) with NAL 20 slice wrapping available for users prioritizing rapid turnarounds.
- **Anaglyph 3D Preview & Orientation Check:**
  - Real-time scrub-bar preview supporting Red/Cyan (Dubois, Full Color, Half Color), Green/Magenta (Trioscopic), and Amber/Blue (ColorCode 3D).
  - One-click **🔄 Swap Left/Right Eyes** toggle to easily fix pseudoscopic/inverted 3D sources before encoding.
  - Bidirectional scrub bar with quick jump presets (`10%`, `50%`, `90%`) and native `ffplay` live stream playback.
- **Aspect Ratio & 2D Compatibility:**
  - Enforces 16:9 square-pixel display dimensions (`setsar=1` and `mkvmerge --display-dimensions 0:1920x1080`), ensuring no squeezed playback on 2D players like VLC or 3D VR headsets.
- **Customizable Theming:**
  - 8 distinct UI themes (4 Clean Light, 4 Modern Dark) with persistent theme memory.
- **Uncapped Bitrate Control:**
  - Presets for VR Streaming (20 Mbps), BD-50 (40 Mbps), BD-25 (23 Mbps), and manual adjustment up to 120+ Mbps.
- **Framerate Compatibility & Authoring Rules:**
  - **Playable Physical 3D Blu-ray Discs:** Must be encoded at **1080p @ 23.976 / 24 fps** (with the 40 Mbps VBV cap) to comply with the Blu-ray Disc Association (BDA) hardware standard for standalone consumer players (Sony, Panasonic, Oppo).
  - **Network / File / VLC4MVC Playback:** If playing from a NAS (SMB/NFS), BD data disc, or USB on Android players (Zidoo, Dune HD, Shield, Ugoos) connected to 3D 4K projectors, **arbitrary native framerates (24, 30, 48 HFR, 50, 60 fps)** and uncapped bitrates are fully supported without physical disc constraints.
- **Lossless Audio Passthrough & True DTS-HD Master Audio (Powered by Subwoofa):**
  - Direct bitstream copy for Dolby Atmos, TrueHD, DTS:X, and DTS-HD Master Audio.
  - Lossless encoding of multi-channel FLAC/WAV audio into bit-perfect, certified **DTS-HD Master Audio 5.1/7.1** (`.dtshd`) bitstreams via Callum's high-speed **Subwoofa** engine ([@callumcomplains](https://github.com/callumcomplains/subwoofa)), multiplexed natively into compliant 3D Blu-ray ISOs.
  - Subwoofa is an integral part of the StereoForge installation package (pre-bundled with the portable distribution and auto-downloaded on launch).

---

## Project Structure

```
StereoForge/
├── STEREOFORGE_SPECIFICATION.md  # Detailed technical specifications and architecture
├── README.md                     # Project overview and setup instructions
├── pyproject.toml                # Project metadata and package setup
├── requirements.txt              # Python dependencies (PySide6, numpy, opencv-python)
├── run_stereoforge.bat           # One-click Windows CMD launcher & auto-installer
├── run_stereoforge.ps1           # Windows PowerShell launcher & auto-installer
├── stereoforge/                  # Core package
│   ├── core/                     # MVC bitstream syntax, manifest, disparity
│   ├── pipeline/                 # Ingestion, Pass 1 GPU, Pass 2 CPU, Muxers
│   └── ui/                       # Qt 6 GUI with themes and anaglyph preview
└── tests/                        # Test suite
```

---

## Credits
* **Conception, UX & Vision:** `writesimply.bcc`
* **Architecture & Code:** `Gemini`
* **DTS-HD Master Audio Engine:** Subwoofa by Callum ([@callumcomplains](https://github.com/callumcomplains/subwoofa))
