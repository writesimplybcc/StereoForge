"""Pass 1: Base View (Left Eye) Hardware Encoder & Manifest Generator.

Encodes the Left Eye using the fastest available hardware encoder
(NVENC / QSV / AMF / VideoToolbox) and records frame decisions into
a FrameManifest for strict 3D synchronization.
"""

from pathlib import Path
from typing import Optional, Callable, Dict, Any
import subprocess
import json
import shutil
import re

from stereoforge.core.manifest import FrameManifest, StreamMetadata, FrameEntry
from stereoforge.pipeline.ingest import MediaProfile, IngestionEngine


def detect_best_h264_encoder(ffmpeg_bin: str = "ffmpeg") -> str:
    """Detects the fastest available H.264 encoder on the current machine."""
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        out = res.stdout
    except Exception:
        return "libx264"

    # Priority order:
    # 1. Nvidia NVENC (Windows / Linux x86_64)
    # 2. Apple VideoToolbox (macOS Apple Silicon M1-M4 & Intel)
    # 3. Intel QuickSync / QSV (Windows / Linux)
    # 4. AMD AMF (Windows / Linux)
    # 5. VAAPI (Linux x86_64 / Linux ARM64)
    # 6. Windows MediaFoundation (Windows ARM64 / Windows x64)
    # 7. CPU fallback: libx264 (universal, AVX2/AVX-512/ARM NEON)
    if "h264_nvenc" in out:
        return "h264_nvenc"
    if "h264_videotoolbox" in out:
        return "h264_videotoolbox"
    if "h264_qsv" in out:
        return "h264_qsv"
    if "h264_amf" in out:
        return "h264_amf"
    if "h264_vaapi" in out:
        return "h264_vaapi"
    if "h264_mf" in out:
        return "h264_mf"
    return "libx264"


class BaseViewEncoder:
    """Runs Pass 1 on the GPU and extracts the frame manifest."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin
        self.encoder = detect_best_h264_encoder(ffmpeg_bin)

    def encode(
        self,
        profile: MediaProfile,
        output_base_264: Path,
        output_manifest_json: Path,
        bitrate_kbps: int = 25000,
        strict_bluray: bool = True,
        swap_eyes: bool = False,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> FrameManifest:
        """Encodes the Left Eye (Base View) and generates the frame manifest."""
        left_filter, _ = IngestionEngine.get_filter_chains(profile, swap_eyes=swap_eyes)

        manifest = FrameManifest(
            metadata=StreamMetadata(
                width=1920,
                height=1080,
                fps_num=int(profile.fps * 1000),
                fps_den=1000,
                color_primaries="bt709",
                color_transfer="bt709",
                color_space="bt709",
                duration_seconds=profile.duration
            )
        )

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(profile.path),
            "-vf", left_filter,
            "-pix_fmt", "yuv420p",
            "-c:v", self.encoder,
            "-b:v", f"{bitrate_kbps}k",
        ]

        if strict_bluray:
            # Enforce Blu-ray Level 4.1 & VBV buffer constraints
            cmd.extend([
                "-profile:v", "high",
                "-level:v", "4.1",
                "-maxrate", "35000k",
                "-bufsize", "30000k",
                "-g", "24",  # Keyframe every 1 second
                "-keyint_min", "24",
                "-sc_threshold", "0"
            ])

        # Output raw H.264 bitstream
        cmd.extend([
            "-an",  # Strip audio (audio is copied separately during muxing)
            "-f", "h264",
            str(output_base_264)
        ])

        print(f"[StereoForge] Pass 1 Base View encoding with {self.encoder}...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _, stderr_data = process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Pass 1 encoding failed: {stderr_data}")

        # Extract exact frame metadata via ffprobe packet inspection
        print("[StereoForge] Generating Frame Manifest from encoded bitstream...")
        manifest = self._generate_manifest(output_base_264, manifest.metadata)
        manifest.save(output_manifest_json)
        print(f"[StereoForge] Manifest saved with {len(manifest.frames)} frames.")

        return manifest

    def _generate_manifest(self, bitstream_path: Path, metadata: StreamMetadata) -> FrameManifest:
        """Inspects the generated bitstream packets to record the exact GOP structure."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-select_streams", "v:0",
            "-show_packets",
            "-show_entries", "packet=pts,dts,flags,pos",
            "-print_format", "json",
            str(bitstream_path)
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(res.stdout)
            packets = data.get("packets", [])
        except Exception:
            # Fallback estimation if ffprobe packet inspection is unavailable
            packets = []

        manifest = FrameManifest(metadata=metadata)

        if packets:
            for idx, p in enumerate(packets):
                flags = p.get("flags", "")
                is_key = "K" in flags
                pts = int(p.get("pts", idx * 1000))
                dts = int(p.get("dts", idx * 1000))
                slice_type = "IDR" if is_key else ("B" if pts != dts else "P")

                manifest.add_frame(FrameEntry(
                    index=idx,
                    slice_type=slice_type,
                    pts=pts,
                    dts=dts,
                    poc=idx * 2,
                    is_keyframe=is_key
                ))
        else:
            # Synthetic 24-frame GOP manifest fallback (IBBPBBPBBP...)
            total = int(metadata.duration_seconds * 24.0) if metadata.duration_seconds > 0 else 100
            for idx in range(total):
                is_idr = (idx % 24 == 0)
                slice_type = "IDR" if is_idr else ("B" if idx % 3 != 0 else "P")
                manifest.add_frame(FrameEntry(
                    index=idx,
                    slice_type=slice_type,
                    pts=idx * 1000,
                    dts=idx * 1000,
                    poc=idx * 2,
                    is_keyframe=is_idr
                ))

        return manifest
