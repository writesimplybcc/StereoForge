# StereoForge
> **Imagined by writesimply.bcc • Coded by Gemini**

---

## 1. Executive Summary
**StereoForge** is an open-source, high-performance stereoscopic 3D video encoding and packaging suite. It solves the decade-long drought in consumer and prosumer 3D video authoring caused by the obsolescence of FRIM and the lack of native MVC (Multiview Video Coding) support in mainstream encoders like x264.

StereoForge delivers an all-in-one pipeline: from raw 3D camcorder footage, DaVinci Resolve masters, or Side-by-Side/Top-and-Bottom files to **native 3D Blu-ray ISOs** (for home theater 3D projectors) and **frame-packed 3D MVC MKVs** (for Meta Quest, Apple Vision Pro, and PCVR).

---

## 2. Core Architecture: The "Hybrid Option C" Pipeline

StereoForge utilizes a decoupled, heterogeneous pipeline that maximizes the capabilities of modern hardware while preventing race conditions and zero-byte temporary file bloat.

```
[ INPUT MEDIA ]
(SBS / TAB / Dual Left+Right / 2000s 3D Camcorder / ProRes / DNxHR / MKV / MP4)
       |
       v
+--------------------------------------------------------------------------+
| TIER 1: INGESTION & NORMALIZATION (FFmpeg / libav)                       |
| - Auto-detects 3D layout (Full-SBS, Half-SBS, TAB, Dual Files, 3D-AVI).  |
| - Automatic HDR-to-SDR Tone Mapping (BT.2020/PQ -> BT.709 8-bit).        |
| - Splits audio/subtitles for 100% lossless passthrough.                  |
| - Feeds normalized YUV420p frame streams to encoders.                    |
+--------------------------------------------------------------------------+
       |                                          |
       | (Left Eye Raw Frames)                    | (Right Eye Raw Frames)
       v                                          |
+--------------------------------------+          |
| TIER 2: PASS 1 - BASE VIEW (GPU)     |          |
| - High-speed hardware encoder        |          |
|   (Nvidia NVENC / Intel QSV /        |          |
|    Apple VideoToolbox / AMD AMF)     |          |
| - Produces:                          |          |
|   1. `left.264` (Base View Stream)   |          |
|   2. `frame_manifest.log` (GOP, POC, |          |
|       PTS/DTS, slice types I/P/B)    |          |
+--------------------------------------+          |
       |                                          |
       +-----------------------+                  |
                               |                  |
                               v                  v
+--------------------------------------------------------------------------+
| TIER 3: PASS 2 - DEPENDENT VIEW (100% CPU MVC Engine)                    |
| - Hardware GPU Decoder decodes `left.264` to reconstructed YUV (0% CPU). |
| - Ingests Right Eye raw frames + Reconstructed Left Eye frames.          |
| - Slaved to `frame_manifest.log` (100% GOP and slice synchronization).   |
| - Executes horizontal disparity estimation against Left Eye frames.      |
| - Encodes into Annex H MVC: Subset SPS + NAL Unit Type 20 slices.        |
| - Produces: `right.mvc` (Dependent View Stream).                         |
+--------------------------------------------------------------------------+
       |                                          |
       +--------------------+---------------------+
                            |
                            v
+--------------------------------------------------------------------------+
| TIER 4: PACKAGING & MULTIPLEXING (Internal Background Automation)        |
| - Ingests `left.264` + `right.mvc` + untouched Audio + `.sup` Subtitles. |
| - Output Mode A: `tsMuxeR` -> 3D Blu-ray BDMV / ISO (Physical Discs).    |
| - Output Mode B: `mkvmerge` -> 3D Stereoscopic MKV (VR / Media Players). |
+--------------------------------------------------------------------------+
       |
       v
[ FINAL 3D PLAYABLE MEDIA ]
```

---

## 3. Top Features & Problem Solvers

### 3.1. Replaces the Bottlenecks of FRIM
* **No Intel Media SDK Lock-in:** 100% open-source C/C++ engine.
* **Modern Multithreading:** Fully saturates modern 8, 16, 24, and 32-core CPUs with AVX2, AVX-512, and ARM NEON vectorization.
* **64-bit Native:** Eliminates 32-bit Out-Of-Memory crashes on full-length feature films.
* **No AviSynth / DirectShow requirement:** Direct file reading via FFmpeg.

### 3.2. Automatic Inverted Eyes (Pseudoscopic) Detection
* **The Problem:** Inverted left/right eyes cause severe nausea and headache.
* **The Solution:** An integrated optical flow disparity analyzer checks horizontal parallax on sample frames during import. If divergent background parallax is detected, StereoForge alerts the user and offers a one-click **[Swap Eyes]** fix before encoding begins.

### 3.3. Real-Time Dubois Anaglyph Preview Window
* Integrated scrub bar allows users to inspect any point in the video.
* Renders real-time Red/Cyan Dubois Anaglyph, Side-by-Side, or Difference views so users with cheap 3D glasses can visually verify depth and alignment before committing to a 30-minute encode.

### 3.4. Uncapped Bitrate Control + Sane Presets
* **Strict BD-50 (Disc):** Base ~28 Mbps, MVC ~12 Mbps (40 Mbps VBV-capped for physical discs).
* **Strict BD-25 (Disc):** Base ~16 Mbps, MVC ~7 Mbps (23 Mbps total).
* **VR & Home Streaming (Plex/Quest):** CRF 18–20 VBR for maximum quality-to-size efficiency (often smaller than input Full-SBS).
* **Uncapped Power-User Meter:** Continuous slider allowing bitrates up to 120+ Mbps or ultra-low CRF (12–14) for pristine archival and high-end VR headsets.

### 3.5. 100% Lossless Audio & Subtitle Passthrough
* **Audio:** Bitstream copy (`-c:a copy`) for Dolby Atmos, Dolby TrueHD, DTS:X, DTS-HD Master Audio, LPCM, AC-3, E-AC-3, and AAC. Preserves PTS audio delay timestamps.
* **Subtitles:** Native support for `.SUP` / PGS Blu-ray bitmap subtitles, preserving 3D plane offset sequences so subtitles float at proper stereoscopic depth.

### 3.6. Legacy 2000s 3D Camera Restoration
* Natively imports multi-stream 3D-AVIs (Fujifilm FinePix Real 3D W1/W3, Nintendo 3DS).
* Natively imports AVCHD 3D `.MTS` / `.M2TS` (Sony TD10/TD20/TD30, JVC Everio).
* Motion-adaptive deinterlacing (`bwdif`) converts legacy 1080/60i home videos into smooth 1080/60p modern 3D.

---

## 4. Cross-Platform Target Matrix

| Operating System | Architectures | Pass 1 GPU Acceleration | Pass 2 CPU Optimizations | Packaging |
| :--- | :--- | :--- | :--- | :--- |
| **Windows** | x86_64, ARM64 | Nvidia NVENC, Intel QSV, AMD AMF | AVX2, AVX-512, ARM64 NEON | Installer / Portable `.exe` |
| **macOS** | Apple Silicon (M-series), Intel | Apple VideoToolbox | ARM64 NEON, x86_64 AVX2 | Universal `.dmg` |
| **Linux** | x86_64, aarch64 | Nvidia NVENC, VA-API | AVX2, AVX-512, ARM64 NEON | AppImage / Flatpak |

---

## 5. Development Roadmap

### Phase 1: The MVC Core Engine (`stereoforge-core`)
- [ ] Fork minimal x264 core bitstream engine.
- [ ] Implement Annex H bitstream syntax: Subset SPS and Prefix NAL (Type 14).
- [ ] Implement Coded Slice Extension (NAL Unit Type 20) writer.
- [ ] Implement inter-view reference injection: allow the encoder to accept external reconstructed Left Eye YUV frames into `RefPicList0`.
- [ ] Verify elementary `.mvc` bitstream syntax using `edge264-mvc` and `tsMuxeR`.

### Phase 2: Ingestion, Manifest & Hardware Pipeline (`stereoforge-pipe`)
- [ ] Build FFmpeg ingestion wrapper: auto-crop SBS/TAB, demux dual files, decode legacy 3D-AVI.
- [ ] Implement GPU Pass 1 runner (NVENC/QSV/VideoToolbox) generating `left.264`.
- [ ] Implement `frame_manifest.log` generator (recording frame types, POC, PTS/DTS).
- [ ] Build the GPU-accelerated decoder bridge to feed reconstructed Left frames to Pass 2.

### Phase 3: Multiplexing Automation
- [ ] Integrate background orchestration for `tsMuxeR` (generating 3D Blu-ray BDMV / ISO).
- [ ] Integrate background orchestration for `mkvmerge` (generating 3D MVC Matroska with `StereoMode=1`).
- [ ] Implement audio stream-copy and `.SUP` PGS subtitle injection.

### Phase 4: Graphical User Interface (`stereoforge-gui`)
- [ ] Build clean, responsive Qt 6 (PySide6 / C++) desktop interface.
- [ ] Implement drag-and-drop landing zones for SBS, TAB, and Dual files.
- [ ] Implement Dubois Anaglyph preview player with real-time scrub bar.
- [ ] Implement automated optical flow disparity check for inverted eye detection.
- [ ] Implement Preset switcher + Uncapped Bitrate Slider.

---

## 6. Credits
* **Conception, UX & Vision:** writesimply.bcc
* **Architecture & Code:** Gemini
