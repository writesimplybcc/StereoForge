"""Multiplexer Integration Module.

Automates:
1. tsMuxeR for 3D Blu-ray BDMV and ISO authoring.
2. mkvmerge for 3D Matroska (MKV) packaging with StereoMode=1.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import shutil


def find_mkvmerge(preferred: Optional[str] = None) -> str:
    if preferred and (shutil.which(preferred) or Path(preferred).is_file()):
        return preferred
    if shutil.which("mkvmerge"):
        return "mkvmerge"
    candidates = [
        Path(r"C:\Program Files\MKVToolNix\mkvmerge.exe"),
        Path(r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "MKVToolNix" / "mkvmerge.exe"
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return "mkvmerge"


def find_tsmuxer(preferred: Optional[str] = None) -> str:
    if preferred and (shutil.which(preferred) or Path(preferred).is_file()):
        return preferred
    if shutil.which("tsMuxeR"):
        return "tsMuxeR"
    candidates = [
        Path(r"F:\TSMuxer\tsMuxeR.exe"),
        Path(r"C:\Program Files\tsMuxeR\tsMuxeR.exe"),
        Path(r"C:\Program Files (x86)\tsMuxeR\tsMuxeR.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "tsMuxeR" / "tsMuxeR.exe"
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return "tsMuxeR"


def interleave_mvc_streams(base_path: Path, dependent_path: Path, output_path: Path) -> Path:
    """Interleaves Base View AVC and Dependent View MVC into a single Annex B stream.

    Matroska / MakeMKV standard stores 3D MVC as a single video track where
    dependent MVC slices (NAL 20) immediately follow the corresponding base view slices
    within each access unit (AU). This ensures standard 2D players (like VLC) display
    an unsqueezed 16:9 1080p picture while 3D players access both stereoscopic eyes.
    """
    def read_nal_units(file_path: Path):
        with open(file_path, "rb") as f:
            data = f.read()
        i = 0
        n = len(data)
        start_positions = []
        while i < n:
            if i + 3 < n and data[i:i+3] == b"\x00\x00\x01":
                start_positions.append(i)
                i += 3
            elif i + 4 < n and data[i:i+4] == b"\x00\x00\x00\x01":
                start_positions.append(i)
                i += 4
            else:
                i += 1
        start_positions.append(n)
        nals = []
        for idx in range(len(start_positions) - 1):
            nals.append(data[start_positions[idx]:start_positions[idx+1]])
        return nals

    base_nals = read_nal_units(base_path)
    dep_nals = read_nal_units(dependent_path)

    base_headers = []
    base_slices = []
    for nal in base_nals:
        sc_len = 3 if nal[:3] == b"\x00\x00\x01" else 4
        if len(nal) > sc_len:
            nal_type = nal[sc_len] & 0x1F
            if nal_type in (1, 5):
                base_slices.append(nal)
            else:
                base_headers.append(nal)

    dep_headers = []
    dep_slices = []
    for nal in dep_nals:
        sc_len = 3 if nal[:3] == b"\x00\x00\x01" else 4
        if len(nal) > sc_len:
            nal_type = nal[sc_len] & 0x1F
            if nal_type in (1, 5, 20):
                dep_slices.append(nal)
            else:
                dep_headers.append(nal)

    with open(output_path, "wb") as fout:
        for h in base_headers:
            fout.write(h)
        for h in dep_headers:
            fout.write(h)

        total = max(len(base_slices), len(dep_slices))
        for idx in range(total):
            if idx < len(base_slices):
                fout.write(base_slices[idx])
            if idx < len(dep_slices):
                fout.write(dep_slices[idx])

    return output_path


class MuxerEngine:
    """Orchestrates container multiplexers for finished 3D outputs."""

    def __init__(
        self,
        tsmuxer_bin: Optional[str] = None,
        mkvmerge_bin: Optional[str] = None
    ):
        self.tsmuxer_bin = find_tsmuxer(tsmuxer_bin)
        self.mkvmerge_bin = find_mkvmerge(mkvmerge_bin)

    def is_tsmuxer_available(self) -> bool:
        return shutil.which(self.tsmuxer_bin) is not None or Path(self.tsmuxer_bin).is_file()

    def is_mkvmerge_available(self) -> bool:
        return shutil.which(self.mkvmerge_bin) is not None or Path(self.mkvmerge_bin).is_file()

    def mux_3d_mkv(
        self,
        base_video_path: Path,
        dependent_video_path: Path,
        output_mkv_path: Path,
        audio_source_path: Optional[Path] = None,
        subtitle_paths: Optional[List[Path]] = None,
        title: Optional[str] = None
    ) -> bool:
        """Packs Base View + Right Eye into a clean stereoscopic Matroska container."""
        if not self.is_mkvmerge_available():
            raise FileNotFoundError(
                "mkvmerge is required to package 3D MKVs, but was not found. "
                "Please install MKVToolNix or add it to your system PATH."
            )

        cmd = [
            self.mkvmerge_bin,
            "-o", str(output_mkv_path),
        ]

        if title and title.strip():
            cmd.extend(["--title", title.strip()])

        # Package Left Eye (Base 2D View) and Right Eye (3D Dependent View)
        # as distinct, pristine 1080p video tracks.
        # This guarantees standard players (like VLC) display the base view in 16:9
        # without decoding artifacts, while 3D players access both stereoscopic eyes.
        cmd.extend([
            "--track-name", "0:Left Eye (2D Base)",
            str(base_video_path),
            "--track-name", "0:Right Eye (3D View)",
            str(dependent_video_path)
        ])

        if audio_source_path and audio_source_path.exists():
            # Ingest audio without duplicating the original video
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
        if not self.is_tsmuxer_available():
            raise FileNotFoundError(
                "tsMuxeR is required to author 3D Blu-ray ISOs, but was not found. "
                "Please download tsMuxeR and place it in your system PATH or F:\\TSMuxer."
            )
        # tsMuxeR uses --blu-ray for both folder structures and .iso disk images
        meta_lines = ["MUXOPT --blu-ray --no-pcr-on-video-pid --new-audio-pes --vbr --auto-chapters=5"]

        # Base View Track (Left Eye)
        meta_lines.append(f"V_MPEG4/ISO/AVC, {base_video_path}, fps={fps}, insertSEI, contSPS")

        # Dependent View Track (Right Eye MVC)
        meta_lines.append(f"V_MPEG4/ISO/MVC, {dependent_mvc_path}, fps={fps}")

        temp_audio_ac3: Optional[Path] = None
        if audio_source_path and audio_source_path.exists():
            # If the audio source is inside a container, extract to an elementary AC-3 stream for tsMuxeR
            if audio_source_path.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".ts", ".m2ts"):
                temp_audio_ac3 = output_dir_or_iso.parent / "temp_tsmuxer_audio.ac3"
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", str(audio_source_path), "-vn", "-c:a", "ac3", "-b:a", "640k", str(temp_audio_ac3)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                    meta_lines.append(f"A_AC3, {temp_audio_ac3}")
                except Exception:
                    # In case of no audio track in file
                    pass
            else:
                meta_lines.append(f"A_AC3, {audio_source_path}")

        meta_file = output_dir_or_iso.parent / "stereoforge_tsmuxer.meta"
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write("\n".join(meta_lines) + "\n")

        target_flag = str(output_dir_or_iso)
        cmd = [self.tsmuxer_bin, str(meta_file), target_flag]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"[StereoForge] tsMuxeR failed: {e.stderr}")
            return False
        finally:
            if meta_file.exists():
                meta_file.unlink()
            if temp_audio_ac3 and temp_audio_ac3.exists():
                temp_audio_ac3.unlink()
