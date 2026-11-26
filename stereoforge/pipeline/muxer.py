"""Multiplexer Integration Module.

Automates:
1. tsMuxeR for 3D Blu-ray BDMV and ISO authoring.
2. mkvmerge for 3D Matroska (MKV) packaging with StereoMode=1.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import shutil


class MuxerEngine:
    """Orchestrates container multiplexers for finished 3D outputs."""

    def __init__(
        self,
        tsmuxer_bin: str = "tsMuxeR",
        mkvmerge_bin: str = "mkvmerge"
    ):
        self.tsmuxer_bin = tsmuxer_bin
        self.mkvmerge_bin = mkvmerge_bin

    def is_tsmuxer_available(self) -> bool:
        return shutil.which(self.tsmuxer_bin) is not None

    def is_mkvmerge_available(self) -> bool:
        return shutil.which(self.mkvmerge_bin) is not None

    def mux_3d_mkv(
        self,
        base_video_path: Path,
        dependent_mvc_path: Path,
        output_mkv_path: Path,
        audio_source_path: Optional[Path] = None,
        subtitle_paths: Optional[List[Path]] = None,
        title: str = "3D Stereoscopic Video"
    ) -> bool:
        """Packs Base View + Dependent MVC into a 3D Matroska container."""
        cmd = [
            self.mkvmerge_bin,
            "-o", str(output_mkv_path),
            "--title", title,
            # Set Stereoscopic 3D mode (1 = both views, base + dependent)
            "--stereo-mode", "0:1",
            str(base_video_path),
            str(dependent_mvc_path)
        ]

        if audio_source_path and audio_source_path.exists():
            # Ingest audio without re-encoding video
            cmd.extend(["-D", str(audio_source_path)])

        if subtitle_paths:
            for sub in subtitle_paths:
                if sub.exists():
                    cmd.append(str(sub))

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"[StereoForge] MKV muxing failed: {e.stderr}")
            return False

    def mux_3d_bluray(
        self,
        base_video_path: Path,
        dependent_mvc_path: Path,
        output_dir_or_iso: Path,
        audio_source_path: Optional[Path] = None,
        fps: str = "23.976",
        is_iso: bool = True
    ) -> bool:
        """Generates a tsMuxeR meta script and authors a 3D Blu-ray structure or ISO."""
        meta_lines = ["MUXOPT --no-pcr-on-video-pid --new-audio-pes --demux --vbr --auto-chapters=5"]

        # Base View Track (Left Eye)
        meta_lines.append(f"V_MPEG4/ISO/AVC, {base_video_path}, fps={fps}, insertSEI, contSPS")

        # Dependent View Track (Right Eye MVC)
        meta_lines.append(f"V_MPEG4/ISO/MVC, {dependent_mvc_path}, fps={fps}")

        # Audio Track passthrough if provided
        if audio_source_path and audio_source_path.exists():
            meta_lines.append(f"A_AC3, {audio_source_path}")

        meta_file = output_dir_or_iso.parent / "stereoforge_tsmuxer.meta"
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write("\n".join(meta_lines) + "\n")

        target_flag = str(output_dir_or_iso)
        cmd = [self.tsmuxer_bin, str(meta_file), target_flag]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return True
        except Exception as e:
            print(f"[StereoForge] tsMuxeR failed: {e}")
            return False
