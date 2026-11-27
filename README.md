# StereoForge
> **Imagined by writesimply.bcc • Coded by Gemini**

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
   * Simply double-click **`run_stereoforge.bat`** (or execute `.\run_stereoforge.ps1` in PowerShell).
   * The launcher automatically locates Python, installs missing Python dependencies from `requirements.txt`, auto-detects FFmpeg/MKVToolNix/tsMuxeR, and opens the GUI.

---

## Prerequisites & External Tools

StereoForge relies on a few standard tools for hardware encoding, container packaging, and disc authoring:

| Tool | Purpose | Quick Installation (Windows PowerShell) |
| :--- | :--- | :--- |
| **Python 3.10+** | Core runtime | `winget install Python.Python.3.12` |
| **FFmpeg** | Video decode, encode & preview | `winget install Gyan.FFmpeg` |
| **MKVToolNix** | 3D MVC Matroska (.mkv) packaging | `winget install MKVToolNix.MKVToolNix` |
| **tsMuxeR** *(Optional)* | 3D Blu-ray ISO / BDMV authoring | Download from [tsMuxer GitHub](https://github.com/justdan96/tsMuxer) and place `tsMuxeR.exe` in `StereoForge/tools` or system PATH |

> **Note on Tool Discovery:** StereoForge automatically scans standard directories (including `C:\Program Files\MKVToolNix`, `C:\ffmpeg\bin`, `StereoForge\tools\`, `StereoForge\bin\`, and system `PATH`). You do not need to manually configure environment variables if tools are installed in their standard locations.

---

## Key Features

- **Hybrid Option C Architecture:**
  - **Pass 1 (GPU Hardware):** Left Eye encoded at 300–500+ fps via hardware acceleration (Nvidia NVENC, Intel QSV, AMD AMF, Apple VideoToolbox), generating a frame manifest.
  - **Pass 2 (100% CPU):** Right Eye MVC encoded utilizing all CPU threads (AVX2, AVX-512, and ARM NEON), slaved to the manifest and referencing GPU-decoded left-eye frames.
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
- **Lossless Audio Passthrough:**
  - Direct bitstream copy for Dolby Atmos, TrueHD, DTS:X, and DTS-HD Master Audio.

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
