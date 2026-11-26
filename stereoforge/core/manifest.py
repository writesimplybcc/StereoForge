"""Frame Manifest Tracker for Option C Hybrid Pipeline.

Records the GOP cadence, slice types (IDR, I, P, B), POC (Picture Order Count),
and PTS/DTS from the GPU Base View pass, ensuring the CPU Dependent View pass
mirrors the exact structure for 100% Blu-ray 3D and MVC compliance.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import json
from pathlib import Path


@dataclass
class FrameEntry:
    index: int
    slice_type: str  # "IDR", "I", "P", "B"
    pts: int
    dts: int
    poc: int
    is_keyframe: bool = False
    duration: Optional[float] = None


@dataclass
class StreamMetadata:
    width: int
    height: int
    fps_num: int
    fps_den: int
    color_primaries: str = "bt709"
    color_transfer: str = "bt709"
    color_space: str = "bt709"
    total_frames: int = 0
    duration_seconds: float = 0.0


class FrameManifest:
    """Manages recording and reading frame decisions between Pass 1 and Pass 2."""

    def __init__(self, metadata: Optional[StreamMetadata] = None):
        self.metadata = metadata or StreamMetadata(1920, 1080, 24000, 1001)
        self.frames: List[FrameEntry] = []

    def add_frame(self, entry: FrameEntry) -> None:
        self.frames.append(entry)
        self.metadata.total_frames = len(self.frames)

    def get_frame(self, index: int) -> Optional[FrameEntry]:
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None

    def save(self, filepath: str | Path) -> None:
        """Saves the manifest to a clean JSON file."""
        data = {
            "metadata": asdict(self.metadata),
            "frames": [asdict(f) for f in self.frames],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str | Path) -> "FrameManifest":
        """Loads a manifest from JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = StreamMetadata(**data["metadata"])
        manifest = cls(metadata=meta)
        manifest.frames = [FrameEntry(**f) for f in data["frames"]]
        return manifest

    def summary(self) -> Dict[str, Any]:
        """Provides GOP statistics for compliance checking."""
        idr_count = sum(1 for f in self.frames if f.slice_type == "IDR")
        i_count = sum(1 for f in self.frames if f.slice_type == "I")
        p_count = sum(1 for f in self.frames if f.slice_type == "P")
        b_count = sum(1 for f in self.frames if f.slice_type == "B")
        return {
            "total_frames": len(self.frames),
            "idr_frames": idr_count,
            "i_frames": i_count,
            "p_frames": p_count,
            "b_frames": b_count,
            "width": self.metadata.width,
            "height": self.metadata.height,
            "fps": self.metadata.fps_num / self.metadata.fps_den,
        }
