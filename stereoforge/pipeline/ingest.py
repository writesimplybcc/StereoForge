"""Media Ingestion & Layout Normalizer.

Detects 3D layout (Full-SBS, Half-SBS, TAB, Dual Files, 3D-AVI),
checks for HDR/10-bit color, and constructs clean FFmpeg filter graphs.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import json
import subprocess
import re


def find_matching_eye_file(left_path: Path) -> Optional[Path]:
    """Finds an accompanying Right Eye video file in the same directory."""
    name = left_path.name
    parent = left_path.parent
    patterns = [
        (re.compile(r"([_\-\.]?)left([_\-\.]?)", re.IGNORECASE), r"\1right\2"),
        (re.compile(r"([_\-\.])l([_\-\.])", re.IGNORECASE), r"\1r\2"),
        (re.compile(r"([_\-\.])l(\.[^.]+)$", re.IGNORECASE), r"\1r\2"),
        (re.compile(r"([_\-\.])left(\.[^.]+)$", re.IGNORECASE), r"\1right\2"),
        (re.compile(r"([_\-\.]?)eye[_\-\.]?1([_\-\.]?)", re.IGNORECASE), r"\1eye_2\2"),
        (re.compile(r"([_\-\.]?)cam[_\-\.]?1([_\-\.]?)", re.IGNORECASE), r"\1cam_2\2"),
    ]
    for pattern, repl in patterns:
        if pattern.search(name):
            cand_name = pattern.sub(repl, name)
            for item in parent.iterdir():
                if item.name.lower() == cand_name.lower() and item != left_path:
                    return item
    return None


class StereoFormat(Enum):
    FULL_SBS = "full_sbs"       # Side-by-Side full resolution (e.g. 3840x1080)
    HALF_SBS = "half_sbs"       # Side-by-Side half resolution (e.g. 1920x1080)
    FULL_TAB = "full_tab"       # Top-and-Bottom / Over-Under full res (e.g. 1920x2160)
    HALF_TAB = "half_tab"       # Top-and-Bottom half res (e.g. 1920x1080)
    DUAL_FILES = "dual_files"   # Separate Left and Right video files
    MULTI_STREAM_AVI = "3d_avi" # Legacy 2000s Fuji W1/W3, Nintendo 3DS (dual video streams)
    UNKNOWN = "unknown"


@dataclass
class MediaProfile:
    path: Path
    width: int
    height: int
    fps: float
    fps_str: str
    duration: float
    codec: str
    pix_fmt: str
    is_10bit: bool
    is_hdr: bool
    stereo_format: StereoFormat
    audio_tracks: int
    subtitle_tracks: int
    is_interlaced: bool = False
    is_8k: bool = False
    audio_streams: List[Dict[str, Any]] = field(default_factory=list)
    subtitle_streams: List[Dict[str, Any]] = field(default_factory=list)


class IngestionEngine:
    """Probes media files and generates FFmpeg extraction pipelines."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def probe(self, filepath: Path) -> MediaProfile:
        """Probes a video file using FFprobe or FFmpeg."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(filepath)
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(res.stdout)
        except Exception:
            # Fallback default profile if ffprobe is not in path directly
            return MediaProfile(
                path=filepath,
                width=1920,
                height=1080,
                fps=23.976,
                fps_str="24000/1001",
                duration=0.0,
                codec="h264",
                pix_fmt="yuv420p",
                is_10bit=False,
                is_hdr=False,
                stereo_format=StereoFormat.UNKNOWN,
                audio_tracks=1,
                subtitle_tracks=0
            )

        video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
        sub_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "subtitle"]

        width = int(video_stream.get("width", 1920))
        height = int(video_stream.get("height", 1080))
        pix_fmt = video_stream.get("pix_fmt", "yuv420p")
        color_primaries = video_stream.get("color_primaries", "").lower()
        color_transfer = video_stream.get("color_trc", "").lower()

        is_10bit = "10" in pix_fmt or "p010" in pix_fmt
        is_hdr = is_10bit and (
            "bt2020" in color_primaries or "arib" in color_primaries or
            "smpte2084" in color_transfer or "arib-std-b67" in color_transfer
        )

        field_order = video_stream.get("field_order", "progressive").lower()
        is_interlaced = field_order in ("tt", "bb", "tb", "bt") or video_stream.get("interlaced_frame", 0) == 1

        # Detect 3D Layout heuristic based on metadata tags, filename hints, and aspect ratio
        stereo_format = StereoFormat.UNKNOWN
        video_count = sum(1 for s in data.get("streams", []) if s.get("codec_type") == "video")
        filename_lower = filepath.name.lower()
        aspect = width / max(1, height)

        # Check stream/format metadata tags & side data for explicit 3D flags
        stream_tags = video_stream.get("tags", {})
        format_tags = data.get("format", {}).get("tags", {})
        tag_blob = " ".join([str(v) for v in list(stream_tags.values()) + list(format_tags.values())]).lower()

        matching_right = find_matching_eye_file(filepath)
        if matching_right:
            stereo_format = StereoFormat.DUAL_FILES
        elif video_count > 1 and filepath.suffix.lower() == ".avi":
            stereo_format = StereoFormat.MULTI_STREAM_AVI
        elif any(k in tag_blob for k in ["top_bottom", "topbottom", "over_under", "overunder", "tab", "hou"]):
            stereo_format = StereoFormat.FULL_TAB if aspect <= 1.0 else StereoFormat.HALF_TAB
        elif any(k in tag_blob for k in ["side_by_side", "sidebyside", "left_right", "sbs", "hsbs"]):
            stereo_format = StereoFormat.FULL_SBS if aspect >= 3.0 else StereoFormat.HALF_SBS
        elif any(k in filename_lower for k in ["tab", "overunder", "over-under", "topbottom", "top-bottom", "_ou", "-ou", "hou", "fou"]):
            stereo_format = StereoFormat.FULL_TAB if aspect <= 1.0 else StereoFormat.HALF_TAB
        elif any(k in filename_lower for k in ["sbs", "sidebyside", "side-by-side", "half-sbs", "hsbs", "fsbs"]):
            stereo_format = StereoFormat.FULL_SBS if aspect >= 3.0 else StereoFormat.HALF_SBS
        elif aspect >= 3.0 or (width >= 3840 and height <= 1200):
            # Ultra-wide aspect: Full-SBS (e.g. 3840x1080 or 7680x2160)
            stereo_format = StereoFormat.FULL_SBS
        elif aspect <= 1.0 or (height >= 2160 and width <= 2000):
            # Tall aspect: Full-TAB (e.g. 1920x2160 or 3840x4320)
            stereo_format = StereoFormat.FULL_TAB
        elif width >= 3840 and height >= 2160:
            # Standard 4K UHD 16:9 frame packing 3D (default to SBS if no TAB hint)
            stereo_format = StereoFormat.HALF_SBS
        elif width == 1920 and height <= 1080 and aspect > 1.7:
            stereo_format = StereoFormat.HALF_SBS
        elif height > width:
            stereo_format = StereoFormat.HALF_TAB

        # Calculate FPS
        r_frame_rate = video_stream.get("r_frame_rate", "24000/1001")
        try:
            num, den = map(int, r_frame_rate.split("/"))
            fps = num / den
        except Exception:
            fps = 23.976
            r_frame_rate = "24000/1001"

        duration = float(data.get("format", {}).get("duration", 0.0))

        audio_info_list = []
        for i, a in enumerate(audio_streams):
            tags = a.get("tags", {})
            audio_info_list.append({
                "stream_index": a.get("index"),
                "audio_index": i,
                "codec": a.get("codec_name", "unknown").lower(),
                "channels": a.get("channels", 2),
                "channel_layout": a.get("channel_layout", "stereo"),
                "bit_rate": a.get("bit_rate"),
                "sample_rate": a.get("sample_rate"),
                "language": tags.get("language", "und"),
                "title": tags.get("title", ""),
                "tags": tags
            })

        sub_info_list = []
        for i, s in enumerate(sub_streams):
            tags = s.get("tags", {})
            disposition = s.get("disposition", {})
            codec = s.get("codec_name", "unknown").lower()
            sub_info_list.append({
                "stream_index": s.get("index"),
                "sub_index": i,
                "codec": codec,
                "language": tags.get("language", "und"),
                "title": tags.get("title", ""),
                "is_forced": bool(disposition.get("forced", 0)),
                "is_default": bool(disposition.get("default", 0)),
                "tags": tags
            })

        return MediaProfile(
            path=filepath,
            width=width,
            height=height,
            fps=fps,
            fps_str=r_frame_rate,
            duration=duration,
            codec=video_stream.get("codec_name", "unknown"),
            pix_fmt=pix_fmt,
            is_10bit=is_10bit,
            is_hdr=is_hdr,
            is_interlaced=is_interlaced,
            is_8k=(width >= 7680 or height >= 4320),
            stereo_format=stereo_format,
            audio_tracks=len(audio_streams),
            subtitle_tracks=len(sub_streams),
            audio_streams=audio_info_list,
            subtitle_streams=sub_info_list
        )

    @staticmethod
    def get_filter_chains(
        profile: MediaProfile,
        target_w: int = 1920,
        target_h: int = 1080,
        swap_eyes: bool = False
    ) -> Tuple[str, str]:
        """Constructs FFmpeg filter strings for Left Eye and Right Eye extraction.

        Returns:
            Tuple of (left_filter, right_filter)
        """
        fmt = profile.stereo_format

        # Motion-adaptive deinterlacing for 60i/50i camcorders (Sony TD10/TD20/TD30, JVC, Panasonic)
        deint = "bwdif=mode=0:parity=auto:deint=all," if profile.is_interlaced else ""

        # High-performance Lanczos3 anti-aliasing scaling filter for 8K / 4K downsampling to 1080p
        scale_opts = ":flags=lanczos" if (profile.width >= 3840 or profile.height >= 2160 or getattr(profile, 'is_8k', False)) else ""

        if fmt == StereoFormat.FULL_SBS:
            l_crop = f"{deint}crop=iw/2:ih:0:0,scale={target_w}:{target_h}{scale_opts},setsar=1"
            r_crop = f"{deint}crop=iw/2:ih:iw/2:0,scale={target_w}:{target_h}{scale_opts},setsar=1"
        elif fmt == StereoFormat.HALF_SBS:
            l_crop = f"{deint}crop=iw/2:ih:0:0,scale={target_w}:{target_h}{scale_opts},setsar=1"
            r_crop = f"{deint}crop=iw/2:ih:iw/2:0,scale={target_w}:{target_h}{scale_opts},setsar=1"
        elif fmt == StereoFormat.FULL_TAB:
            l_crop = f"{deint}crop=iw:ih/2:0:0,scale={target_w}:{target_h}{scale_opts},setsar=1"
            r_crop = f"{deint}crop=iw:ih/2:0:ih/2,scale={target_w}:{target_h}{scale_opts},setsar=1"
        elif fmt == StereoFormat.HALF_TAB:
            l_crop = f"{deint}crop=iw:ih/2:0:0,scale={target_w}:{target_h}{scale_opts},setsar=1"
            r_crop = f"{deint}crop=iw:ih/2:0:ih/2,scale={target_w}:{target_h}{scale_opts},setsar=1"
        elif fmt == StereoFormat.MULTI_STREAM_AVI:
            l_crop = f"{deint}scale={target_w}:{target_h}{scale_opts},setsar=1"
            r_crop = f"{deint}scale={target_w}:{target_h}{scale_opts},setsar=1"
        else:
            # Passthrough or default 1:1
            l_crop = f"{deint}scale={target_w}:{target_h}{scale_opts},setsar=1"
            r_crop = f"{deint}scale={target_w}:{target_h}{scale_opts},setsar=1"

        # HDR to SDR Tone Mapping if needed
        hdr_filter = ""
        if profile.is_hdr:
            # High-fidelity Mobius / BT.709 tone mapping
            hdr_filter = ",zscale=t=linear:npl=100,tonemap=tonemap=mobius:desat=0,zscale=p=bt709:t=bt709:m=bt709:r=limited,format=yuv420p"
        elif profile.is_10bit:
            # Dither 10-bit SDR down to standard 8-bit YUV420p for Blu-ray / MVC
            hdr_filter = ",format=yuv420p"

        left_chain = l_crop + hdr_filter
        right_chain = r_crop + hdr_filter

        if swap_eyes:
            return right_chain, left_chain
        return left_chain, right_chain

    def extract_stereo_pair(
        self,
        profile: MediaProfile,
        timestamp_sec: float = 10.0,
        target_w: int = 640,
        target_h: int = 360,
        swap_eyes: bool = False,
        right_file: Optional[Path] = None
    ) -> Tuple[Optional[Any], Optional[Any]]:
        """Extracts a synchronized pair of Left and Right RGB images as NumPy arrays."""
        import numpy as np
        l_chain, r_chain = self.get_filter_chains(profile, target_w=target_w, target_h=target_h, swap_eyes=swap_eyes)

        cmd_l = [
            self.ffmpeg_bin, "-y",
            "-ss", str(round(timestamp_sec, 2)),
            "-i", str(profile.path),
        ]
        if profile.stereo_format == StereoFormat.MULTI_STREAM_AVI:
            cmd_l.extend(["-map", "0:v:1" if swap_eyes else "0:v:0"])
        cmd_l.extend([
            "-vf", l_chain,
            "-vframes", "1",
            "-pix_fmt", "rgb24",
            "-f", "rawvideo", "-"
        ])

        r_input = right_file if (right_file and right_file.exists()) else profile.path
        cmd_r = [
            self.ffmpeg_bin, "-y",
            "-ss", str(round(timestamp_sec, 2)),
            "-i", str(r_input),
        ]
        if profile.stereo_format == StereoFormat.MULTI_STREAM_AVI:
            cmd_r.extend(["-map", "0:v:0" if swap_eyes else "0:v:1"])
        cmd_r.extend([
            "-vf", r_chain,
            "-vframes", "1",
            "-pix_fmt", "rgb24",
            "-f", "rawvideo", "-"
        ])

        expected_bytes = target_w * target_h * 3
        try:
            res_l = subprocess.run(cmd_l, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
            res_r = subprocess.run(cmd_r, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
            if len(res_l.stdout) >= expected_bytes and len(res_r.stdout) >= expected_bytes:
                l_img = np.frombuffer(res_l.stdout[:expected_bytes], dtype=np.uint8).reshape((target_h, target_w, 3))
                r_img = np.frombuffer(res_r.stdout[:expected_bytes], dtype=np.uint8).reshape((target_h, target_w, 3))
                return l_img, r_img
        except Exception:
            pass
        return None, None
