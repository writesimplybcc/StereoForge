"""Multiplexer Integration Module.

Automates:
1. tsMuxeR for 3D Blu-ray BDMV and ISO authoring.
2. mkvmerge for 3D Matroska (MKV) packaging with StereoMode=1.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import shutil
from stereoforge.pipeline.chapters import Chapter, extract_chapters, format_tsmuxer_chapter_option, create_ogm_chapters_file


def find_mkvmerge(preferred: Optional[str] = None) -> str:
    if preferred and (shutil.which(preferred) or Path(preferred).is_file()):
        return preferred
    if shutil.which("mkvmerge"):
        return "mkvmerge"
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "tools" / "mkvmerge.exe",
        repo_root / "bin" / "mkvmerge.exe",
        repo_root / "mkvmerge.exe",
        repo_root / "tools" / "mkvmerge",
        repo_root / "bin" / "mkvmerge",
        repo_root / "mkvmerge",
        # macOS paths (Apple Silicon & Intel Homebrew / MacPorts)
        Path("/opt/homebrew/bin/mkvmerge"),
        Path("/usr/local/bin/mkvmerge"),
        Path("/opt/local/bin/mkvmerge"),
        # Linux standard system paths
        Path("/usr/bin/mkvmerge"),
        Path("/bin/mkvmerge"),
        # Windows standard locations
        Path(r"C:\Program Files\MKVToolNix\mkvmerge.exe"),
        Path(r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "MKVToolNix" / "mkvmerge.exe",
        Path(r"C:\ProgramData\chocolatey\bin\mkvmerge.exe"),
        Path.home() / "scoop" / "apps" / "mkvtoolnix" / "current" / "mkvmerge.exe",
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
    if shutil.which("tsmuxer"):
        return "tsmuxer"
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "tools" / "tsMuxeR.exe",
        repo_root / "bin" / "tsMuxeR.exe",
        repo_root / "tsMuxeR.exe",
        repo_root / "tools" / "tsMuxeR",
        repo_root / "bin" / "tsMuxeR",
        repo_root / "tsMuxeR",
        # macOS paths (Homebrew / local)
        Path("/opt/homebrew/bin/tsMuxeR"),
        Path("/usr/local/bin/tsMuxeR"),
        Path("/Applications/tsMuxeR.app/Contents/MacOS/tsMuxeR"),
        # Linux standard system paths
        Path("/usr/local/bin/tsMuxeR"),
        Path("/usr/bin/tsMuxeR"),
        # Windows standard locations
        Path(r"C:\Program Files\tsMuxeR\tsMuxeR.exe"),
        Path(r"C:\Program Files (x86)\tsMuxeR\tsMuxeR.exe"),
        Path(r"C:\tsMuxeR\tsMuxeR.exe"),
        Path(r"D:\tsMuxeR\tsMuxeR.exe"),
        Path(r"F:\TSMuxer\tsMuxeR.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "tsMuxeR" / "tsMuxeR.exe",
        Path(r"C:\ProgramData\chocolatey\bin\tsMuxeR.exe"),
        Path.home() / "scoop" / "apps" / "tsmuxer" / "current" / "tsMuxeR.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return "tsMuxeR"


def find_subwoofa(preferred: Optional[str] = None) -> str:
    if preferred and (shutil.which(preferred) or Path(preferred).is_file()):
        return preferred
    if shutil.which("subwoofa"):
        return "subwoofa"
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "tools" / "subwoofa-cli.exe",
        repo_root / "tools" / "subwoofa.exe",
        repo_root / "bin" / "subwoofa-cli.exe",
        repo_root / "bin" / "subwoofa.exe",
        repo_root / "subwoofa-cli.exe",
        repo_root / "subwoofa.exe",
        repo_root / "tools" / "subwoofa",
        repo_root / "bin" / "subwoofa",
        repo_root / "subwoofa",
        Path.home() / "AppData" / "Local" / "Subwoofa" / "subwoofa.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "Subwoofa" / "subwoofa.exe",
        Path(r"C:\Program Files\Subwoofa\subwoofa.exe"),
        Path(r"C:\Program Files (x86)\Subwoofa\subwoofa.exe"),
        Path("/opt/homebrew/bin/subwoofa"),
        Path("/usr/local/bin/subwoofa"),
        Path("/usr/bin/subwoofa"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return "subwoofa"


def interleave_mvc_streams(base_path: Path, dependent_path: Path, output_path: Path) -> Path:
    """Interleaves Base View AVC and Dependent View MVC into a single Annex B stream.

    Matroska / MakeMKV standard stores 3D MVC as a single video track where
    dependent MVC slices (NAL 20) immediately follow the corresponding base view slices
    within each access unit (AU). This ensures standard 2D players (like VLC) display
    an unsqueezed 16:9 1080p picture while 3D players access both stereoscopic eyes.
    """
    def read_nal_units(file_path: Path, chunk_size: int = 1024 * 1024):
        nals = []
        with open(file_path, "rb") as f:
            buf = bytearray()
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                buf.extend(chunk)

                sc_list = []
                i = 0
                while True:
                    idx = buf.find(b"\x00\x00\x01", i)
                    if idx == -1:
                        break
                    if idx > 0 and buf[idx - 1] == 0:
                        sc_list.append((idx - 1, 4))
                    else:
                        sc_list.append((idx, 3))
                    i = idx + 3

                if len(sc_list) > 1:
                    for k in range(len(sc_list) - 1):
                        sc_pos = sc_list[k][0]
                        next_sc_pos = sc_list[k + 1][0]
                        nals.append(bytes(buf[sc_pos:next_sc_pos]))
                    buf = buf[sc_list[-1][0]:]

            if buf:
                sc_list = []
                i = 0
                while True:
                    idx = buf.find(b"\x00\x00\x01", i)
                    if idx == -1:
                        break
                    if idx > 0 and buf[idx - 1] == 0:
                        sc_list.append((idx - 1, 4))
                    else:
                        sc_list.append((idx, 3))
                    i = idx + 3
                if sc_list:
                    for k in range(len(sc_list)):
                        sc_pos = sc_list[k][0]
                        next_sc_pos = sc_list[k + 1][0] if k + 1 < len(sc_list) else len(buf)
                        nals.append(bytes(buf[sc_pos:next_sc_pos]))
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
        mkvmerge_bin: Optional[str] = None,
        subwoofa_bin: Optional[str] = None
    ):
        self.tsmuxer_bin = find_tsmuxer(tsmuxer_bin)
        self.mkvmerge_bin = find_mkvmerge(mkvmerge_bin)
        self.subwoofa_bin = find_subwoofa(subwoofa_bin)

    def is_tsmuxer_available(self) -> bool:
        return shutil.which(self.tsmuxer_bin) is not None or Path(self.tsmuxer_bin).is_file()

    def is_mkvmerge_available(self) -> bool:
        return shutil.which(self.mkvmerge_bin) is not None or Path(self.mkvmerge_bin).is_file()

    def is_subwoofa_available(self) -> bool:
        return shutil.which(self.subwoofa_bin) is not None or Path(self.subwoofa_bin).is_file()

    def mux_3d_mkv(
        self,
        base_video_path: Path,
        dependent_video_path: Path,
        output_mkv_path: Path,
        audio_source_path: Optional[Path] = None,
        subtitle_paths: Optional[List[Path]] = None,
        title: Optional[str] = None,
        fps: Optional[str] = None,
        chapters: Optional[List[Chapter]] = None,
        chapter_interval_minutes: Optional[int] = None
    ) -> bool:
        """Packs Base View + Right Eye into a clean stereoscopic Matroska container."""
        fps_str = str(fps) if fps else "24000/1001"
        if not self.is_mkvmerge_available():
            # Fallback to FFmpeg native Matroska stream-copy packaging
            print(f"[StereoForge] mkvmerge not found, using FFmpeg to package stereoscopic Matroska @ {fps_str} fps...")
            cmd = [
                "ffmpeg", "-y",
                "-r", fps_str,
                "-i", str(base_video_path),
                "-r", fps_str,
                "-i", str(dependent_video_path),
            ]
            if audio_source_path and audio_source_path.exists():
                cmd.extend(["-i", str(audio_source_path)])
                cmd.extend([
                    "-map", "0:v", "-map", "1:v", "-map", "2:a?", "-map", "2:s?",
                    "-c", "copy",
                    "-disposition:v:0", "default",
                    "-metadata:s:v:0", "title=Left Eye (2D Base)",
                    "-metadata:s:v:1", "title=Right Eye (3D View)",
                ])
            else:
                cmd.extend([
                    "-map", "0:v", "-map", "1:v",
                    "-c", "copy",
                    "-disposition:v:0", "default",
                    "-metadata:s:v:0", "title=Left Eye (2D Base)",
                    "-metadata:s:v:1", "title=Right Eye (3D View)",
                ])

            if title and title.strip():
                cmd.extend(["-metadata", f"title={title.strip()}"])

            cmd.append(str(output_mkv_path))
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                return True
            except subprocess.CalledProcessError as e:
                print(f"[StereoForge] FFmpeg MKV muxing failed: {e.stderr}")
                return False

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
            "--display-dimensions", "0:1920x1080",
            str(base_video_path),
            "--track-name", "0:Right Eye (3D View)",
            "--display-dimensions", "0:1920x1080",
            str(dependent_video_path)
        ])

        if audio_source_path and audio_source_path.exists():
            # Ingest audio without duplicating the original video
            cmd.extend(["-D", str(audio_source_path)])

        if subtitle_paths:
            for sub in subtitle_paths:
                if sub.exists():
                    cmd.append(str(sub))

        temp_chap_file: Optional[Path] = None
        if not chapters and audio_source_path and audio_source_path.exists():
            chapters = extract_chapters(audio_source_path)

        if chapters:
            temp_chap_file = output_mkv_path.parent / "temp_chapters.txt"
            create_ogm_chapters_file(chapters, temp_chap_file)
            cmd.extend(["--chapters", str(temp_chap_file)])
        elif chapter_interval_minutes and chapter_interval_minutes > 0:
            cmd.extend(["--generate-chapters", f"interval:{chapter_interval_minutes}m"])

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            if temp_chap_file and temp_chap_file.exists():
                temp_chap_file.unlink()
            return True
        except subprocess.CalledProcessError as e:
            if temp_chap_file and temp_chap_file.exists():
                temp_chap_file.unlink()
            print(f"[StereoForge] MKV muxing failed: {e.stderr}")
            return False

    def mux_3d_bluray(
        self,
        base_video_path: Path,
        dependent_mvc_path: Path,
        output_dir_or_iso: Path,
        audio_source_path: Optional[Path] = None,
        audio_streams: Optional[List[Dict[str, Any]]] = None,
        subtitle_streams: Optional[List[Dict[str, Any]]] = None,
        subtitle_paths: Optional[List[Path]] = None,
        fps: str = "23.976",
        is_iso: bool = True,
        chapters: Optional[List[Chapter]] = None,
        chapter_interval_minutes: int = 5
    ) -> bool:
        """Generates a tsMuxeR meta script and authors a 3D Blu-ray structure or ISO.

        Preserves all audio streams with TrueHD/Atmos, DTS-HD MA, and AC3 passthrough.
        Non-Blu-ray audio formats (Opus, AAC, FLAC, Vorbis) are transcoded to standard 640k AC-3.
        """
        if not self.is_tsmuxer_available():
            raise FileNotFoundError(
                "tsMuxeR is required to author 3D Blu-ray ISOs, but was not found. "
                "Please download tsMuxeR (https://github.com/justdan96/tsMuxer) and place tsMuxeR.exe "
                "in your system PATH, C:\\tsMuxeR, or StereoForge\\tools folder."
            )
        if not chapters and audio_source_path and audio_source_path.exists():
            chapters = extract_chapters(audio_source_path)

        chap_opt = format_tsmuxer_chapter_option(chapters, auto_interval_minutes=chapter_interval_minutes)
        # tsMuxeR uses --blu-ray for both folder structures and .iso disk images
        meta_lines = [f"MUXOPT --blu-ray --no-pcr-on-video-pid --new-audio-pes --vbr {chap_opt}"]

        # Base View Track (Left Eye) - Quoted paths with forward slashes for cross-platform tsMuxeR
        base_str = str(base_video_path).replace("\\", "/")
        meta_lines.append(f'V_MPEG4/ISO/AVC, "{base_str}", fps={fps}, insertSEI, contSPS')

        # Dependent View Track (Right Eye MVC)
        dep_str = str(dependent_mvc_path).replace("\\", "/")
        meta_lines.append(f'V_MPEG4/ISO/MVC, "{dep_str}", fps={fps}')

        temp_audio_files: List[Path] = []
        if audio_source_path and audio_source_path.exists():
            streams_to_process = audio_streams
            if streams_to_process is None:
                # Probe audio streams if not explicitly passed
                try:
                    from stereoforge.pipeline.ingest import IngestionEngine
                    probe_prof = IngestionEngine().probe(audio_source_path)
                    streams_to_process = probe_prof.audio_streams
                except Exception:
                    streams_to_process = [{"audio_index": 0, "codec": "unknown", "language": "und"}]

            for a_info in streams_to_process:
                a_idx = a_info.get("audio_index", 0)
                codec = str(a_info.get("codec", "unknown")).lower()
                lang = a_info.get("language", "und")
                lang_param = f", lang={lang}" if lang and lang != "und" else ""

                try:
                    if codec in ("truehd",):
                        temp_file = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.thd"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:a:{a_idx}", "-c:a", "copy", str(temp_file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_audio_files.append(temp_file)
                        a_str = str(temp_file).replace("\\", "/")
                        meta_lines.append(f'A_TRUE-HD, "{a_str}"{lang_param}')
                    elif codec in ("dts", "dts-hd", "dtshd", "dca"):
                        temp_file = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.dts"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:a:{a_idx}", "-c:a", "copy", str(temp_file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_audio_files.append(temp_file)
                        a_str = str(temp_file).replace("\\", "/")
                        meta_lines.append(f'A_DTS, "{a_str}"{lang_param}')
                    elif codec in ("ac3",):
                        temp_file = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.ac3"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:a:{a_idx}", "-c:a", "copy", str(temp_file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_audio_files.append(temp_file)
                        a_str = str(temp_file).replace("\\", "/")
                        meta_lines.append(f'A_AC3, "{a_str}"{lang_param}')
                    elif codec in ("eac3",):
                        temp_file = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.eac3"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:a:{a_idx}", "-c:a", "copy", str(temp_file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_audio_files.append(temp_file)
                        a_str = str(temp_file).replace("\\", "/")
                        meta_lines.append(f'A_EAC3, "{a_str}"{lang_param}')
                    elif codec == "flac" and self.is_subwoofa_available():
                        # Encode FLAC directly to DTS-HD Master Audio using bundled Subwoofa
                        print(f"[StereoForge] Encoding lossless DTS-HD Master Audio (track {a_idx}) via Subwoofa...")
                        temp_wav = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.wav"
                        temp_dtshd = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.dtshd"
                        sr = a_info.get("sample_rate")
                        ar_args = ["-ar", "48000"] if (not sr or int(sr) not in (48000, 96000, 192000)) else []
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:a:{a_idx}", "-c:a", "pcm_s24le"] + ar_args + [str(temp_wav)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_audio_files.append(temp_wav)
                        channels = a_info.get("channels", 2)
                        layout = "5.1" if channels == 6 else ("7.1" if channels == 8 else ("stereo" if channels == 2 else "5.1"))
                        sub_cmd = [
                            self.subwoofa_bin, "encode",
                            "--stream", "dtshd-ma",
                            "--dest", "bluray-primary",
                            "--layout", layout,
                            "--auto-import", str(temp_wav),
                            "-o", str(temp_dtshd)
                        ]
                        subprocess.run(sub_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        temp_audio_files.append(temp_dtshd)
                        a_str = str(temp_dtshd).replace("\\", "/")
                        meta_lines.append(f'A_DTS, "{a_str}"{lang_param}')
                    elif codec in ("flac", "pcm_s16le", "pcm_s24le", "pcm_bluray", "pcm_s32le", "wav"):
                        temp_file = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.wav"
                        # Blu-ray LPCM standard strictly requires 48kHz, 96kHz, or 192kHz sample rates
                        sr = a_info.get("sample_rate")
                        ar_args = ["-ar", "48000"] if (not sr or int(sr) not in (48000, 96000, 192000)) else []
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:a:{a_idx}", "-c:a", "pcm_s16le"] + ar_args + [str(temp_file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_audio_files.append(temp_file)
                        a_str = str(temp_file).replace("\\", "/")
                        meta_lines.append(f'A_LPCM, "{a_str}"{lang_param}')
                    else:
                        # Non-Blu-ray format (Opus, AAC, FLAC, Vorbis, etc.) -> transcode to 640k AC-3
                        temp_file = output_dir_or_iso.parent / f"temp_tsmuxer_audio_{a_idx}.ac3"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:a:{a_idx}", "-c:a", "ac3", "-b:a", "640k", str(temp_file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_audio_files.append(temp_file)
                        a_str = str(temp_file).replace("\\", "/")
                        meta_lines.append(f'A_AC3, "{a_str}"{lang_param}')
                except Exception as e:
                    print(f"[StereoForge] Warning: could not extract/transcode audio track {a_idx} ({codec}): {e}")

        temp_sub_files: List[Path] = []
        subs_to_process = subtitle_streams
        if audio_source_path and audio_source_path.exists() and subs_to_process is None:
            try:
                from stereoforge.pipeline.ingest import IngestionEngine
                subs_to_process = IngestionEngine().probe(audio_source_path).subtitle_streams
            except Exception:
                subs_to_process = []

        if audio_source_path and audio_source_path.exists() and subs_to_process:
            for s_info in subs_to_process:
                s_idx = s_info.get("sub_index", 0)
                codec = str(s_info.get("codec", "unknown")).lower()
                lang = s_info.get("language", "und")
                lang_param = f", lang={lang}" if lang and lang != "und" else ""

                try:
                    if codec in ("hdmv_pgs_subtitle", "pgs", "pgs_subtitle"):
                        temp_sub = output_dir_or_iso.parent / f"temp_tsmuxer_sub_{s_idx}.sup"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:s:{s_idx}", "-c:s", "copy", str(temp_sub)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_sub_files.append(temp_sub)
                        sub_str = str(temp_sub).replace("\\", "/")
                        meta_lines.append(f'S_HDMV/PGS, "{sub_str}"{lang_param}, 3d-plane=0')
                    elif codec in ("subrip", "srt", "ass", "mov_text", "webvtt"):
                        temp_sub = output_dir_or_iso.parent / f"temp_tsmuxer_sub_{s_idx}.srt"
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(audio_source_path), "-map", f"0:s:{s_idx}", "-c:s", "srt", str(temp_sub)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                        )
                        temp_sub_files.append(temp_sub)
                        sub_str = str(temp_sub).replace("\\", "/")
                        meta_lines.append(f'S_TEXT/UTF8, "{sub_str}", font-name="Arial", font-size=60, font-color=0x00FFFFFF, bottom-offset=50{lang_param}')
                except Exception as e:
                    print(f"[StereoForge] Warning: could not extract subtitle track {s_idx} ({codec}): {e}")

        if subtitle_paths:
            for s_path in subtitle_paths:
                if s_path.exists():
                    sub_str = str(s_path).replace("\\", "/")
                    if s_path.suffix.lower() == ".sup":
                        meta_lines.append(f'S_HDMV/PGS, "{sub_str}", 3d-plane=0')
                    elif s_path.suffix.lower() == ".srt":
                        meta_lines.append(f'S_TEXT/UTF8, "{sub_str}", font-name="Arial", font-size=60, font-color=0x00FFFFFF, bottom-offset=50')

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
            for tmp in temp_audio_files:
                if tmp.exists():
                    tmp.unlink()
            for tmp in temp_sub_files:
                if tmp.exists():
                    tmp.unlink()
