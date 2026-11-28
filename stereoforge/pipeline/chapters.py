"""StereoForge: Chapter extraction, parsing, and authoring module.
Supports source chapter preservation (MKV/MP4/M2TS) and auto-generation for tsMuxeR and mkvmerge.
"""

from __future__ import annotations
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Chapter:
    """Represents a single video chapter point."""
    index: int
    start_seconds: float
    title: str = ""

    @property
    def timestamp_hms_ms(self) -> str:
        """Formats seconds into HH:MM:SS.mmm for tsMuxeR and OGM formats."""
        hours = int(self.start_seconds // 3600)
        minutes = int((self.start_seconds % 3600) // 60)
        seconds = self.start_seconds % 60
        sec_int = int(seconds)
        millis = int(round((seconds - sec_int) * 1000))
        if millis >= 1000:
            millis = 999
        return f"{hours:02d}:{minutes:02d}:{sec_int:02d}.{millis:03d}"


def extract_chapters(media_path: Path) -> List[Chapter]:
    """Extracts chapter markers from an input media file via ffprobe."""
    if not media_path.exists():
        return []

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        # Check standard paths
        for candidate in [
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
            r"tools\ffmpeg\bin\ffprobe.exe",
        ]:
            if Path(candidate).is_file():
                ffprobe = candidate
                break

    if not ffprobe:
        return []

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_chapters",
        str(media_path)
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(res.stdout)
        raw_chapters = data.get("chapters", [])
        chapters: List[Chapter] = []

        for i, item in enumerate(raw_chapters):
            start_sec = float(item.get("start_time", 0.0))
            tags = item.get("tags", {})
            title = tags.get("title", f"Chapter {i + 1:02d}")
            chapters.append(Chapter(index=i + 1, start_seconds=start_sec, title=title))

        # Ensure first chapter starts at 00:00:00 if not present
        if chapters and chapters[0].start_seconds > 0.5:
            chapters.insert(0, Chapter(index=0, start_seconds=0.0, title="Chapter 00"))

        return chapters
    except Exception:
        return []


def generate_interval_chapters(duration_seconds: float, interval_minutes: int = 5) -> List[Chapter]:
    """Generates synthetic chapter points at fixed minute intervals."""
    if duration_seconds <= 0 or interval_minutes <= 0:
        return [Chapter(index=1, start_seconds=0.0, title="Chapter 01")]

    interval_sec = interval_minutes * 60.0
    chapters: List[Chapter] = []
    curr = 0.0
    idx = 1
    while curr < duration_seconds:
        chapters.append(Chapter(index=idx, start_seconds=curr, title=f"Chapter {idx:02d}"))
        curr += interval_sec
        idx += 1

    return chapters


def format_tsmuxer_chapter_option(
    chapters: Optional[List[Chapter]] = None,
    auto_interval_minutes: int = 5
) -> str:
    """Formats chapter option string for tsMuxeR .meta file.
    Example: '--custom-chapters=00:00:00.000;00:05:00.000;00:10:00.000'
    or '--auto-chapters=5' if no explicit chapters.
    """
    if chapters and len(chapters) > 1:
        stamps = [c.timestamp_hms_ms for c in chapters]
        return f"--custom-chapters={';'.join(stamps)}"
    return f"--auto-chapters={max(1, auto_interval_minutes)}"


def create_ogm_chapters_file(
    chapters: List[Chapter],
    output_txt_path: Path
) -> Path:
    """Writes an OGM format simple text chapter file for mkvmerge ingestion.
    Example:
        CHAPTER01=00:00:00.000
        CHAPTER01NAME=Chapter 01
        CHAPTER02=00:05:00.000
        CHAPTER02NAME=Chapter 02
    """
    lines: List[str] = []
    for i, c in enumerate(chapters, start=1):
        lines.append(f"CHAPTER{i:02d}={c.timestamp_hms_ms}")
        lines.append(f"CHAPTER{i:02d}NAME={c.title or f'Chapter {i:02d}'}")

    output_txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_txt_path
