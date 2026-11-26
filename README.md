# StereoForge
> **Imagined by writesimply.bcc • Coded by Gemini**

---

StereoForge is an open-source, high-performance stereoscopic 3D video encoder and packaging suite. It replaces legacy, discontinued tools (such as FRIM) with a modern hybrid GPU + multi-core CPU architecture.

StereoForge converts 3D videos (Side-by-Side, Top-and-Bottom, dual-camera files, or legacy 2000s 3D camcorder footage) into:
1. **3D Blu-ray ISOs / BDMV** (for home theater 3D projectors and physical discs).
2. **3D MVC Matroska (.mkv)** (for Meta Quest, Apple Vision Pro, Bigscreen VR, Skybox, and 4XVR).

---

## Key Features

- **Hybrid Option C Architecture:**
  - **Pass 1 (GPU Hardware):** Left Eye encoded at 300–500+ fps via hardware acceleration (Nvidia NVENC, Intel QSV, AMD AMF, Apple VideoToolbox), generating a frame manifest.
  - **Pass 2 (100% CPU):** Right Eye MVC encoded utilizing all CPU threads (AVX2, AVX-512, and ARM NEON), slaved to the manifest and referencing GPU-decoded left-eye frames.
- **Automatic Inverted-Eye (Pseudoscopic) Detection:** Analyzes horizontal optical flow/parallax and alerts the user if the left and right eyes are inverted, with a one-click fix.
- **Real-Time Dubois Anaglyph Preview:** Integrated scrub-bar preview supporting Red/Cyan anaglyph, Side-by-Side, and Difference views.
- **Lossless Audio Passthrough:** Direct bitstream copy for Dolby Atmos, TrueHD, DTS:X, and DTS-HD Master Audio.
- **Subtitle Support:** Full support for `.SUP` / PGS subtitles with 3D depth plane offsets.
- **Uncapped Bitrate Control:** Sane presets for BD-50, BD-25, and VR streaming, plus an uncapped manual slider up to 120+ Mbps.
- **Legacy 3D Camcorder Support:** Ingests dual-stream 3D-AVI (Fujifilm W1/W3, Nintendo 3DS) and AVCHD 3D `.MTS` (Sony TD10/TD20/TD30).

---

## Project Structure

```
StereoForge/
├── STEREOFORGE_SPECIFICATION.md  # Detailed technical specifications and architecture
├── README.md                     # Project overview and instructions
├── pyproject.toml                # Project metadata and package setup
├── requirements.txt              # Python dependencies
├── stereoforge/                  # Core package
│   ├── core/                     # MVC bitstream syntax, manifest, disparity
│   ├── pipeline/                 # Ingestion, Pass 1 GPU, Pass 2 CPU, Muxers
│   └── ui/                       # Qt 6 GUI with anaglyph preview
└── tests/                        # Test suite
```

---

## Credits
* **Conception, UX & Vision:** `writesimply.bcc`
* **Architecture & Code:** `Gemini`
