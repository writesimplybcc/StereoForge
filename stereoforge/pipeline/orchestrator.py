"""End-to-End Pipeline Orchestrator for StereoForge.

Executes the full pipeline:
1. Probe & normalize input media (SBS, TAB, 3D-AVI, Dual files).
2. Pass 1: Encode Base View (Left Eye) on GPU + generate Frame Manifest.
3. Pass 2: Encode Dependent View (Right Eye MVC) on CPU slaved to Manifest.
4. Tier 4: Multiplex with audio & subtitles into 3D MKV or 3D Blu-ray ISO.
5. Clean up temporary elementary streams.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
import tempfile
import time

from stereoforge.pipeline.ingest import IngestionEngine, MediaProfile, StereoFormat
from stereoforge.pipeline.pass1_base import BaseViewEncoder
from stereoforge.pipeline.pass2_dependent import DependentViewEncoder
from stereoforge.pipeline.muxer import MuxerEngine


@dataclass
class EncodeJob:
    input_file: Path
    output_file: Path
    right_file: Optional[Path] = None
    target_bitrate_mbps: int = 35
    split_ratio_base: float = 0.70  # 70% Base, 30% Dependent
    strict_bluray: bool = True
    swap_eyes: bool = False
    title: Optional[str] = None
    layout_override: Optional[StereoFormat] = None


class StereoForgePipeline:
    """The master pipeline runner for StereoForge."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ingest = IngestionEngine(ffmpeg_bin)
        self.base_encoder = BaseViewEncoder(ffmpeg_bin)
        self.dep_encoder = DependentViewEncoder(ffmpeg_bin)
        self.muxer = MuxerEngine()

    def run(
        self,
        job: EncodeJob,
        progress_cb: Optional[Callable[[str, float], None]] = None
    ) -> bool:
        """Executes the complete encode job from start to finish."""
        start_time = time.time()

        def report(msg: str, pct: float):
            print(f"[StereoForge] {pct*100:5.1f}% - {msg}")
            if progress_cb:
                progress_cb(msg, pct)

        report("Probing input media...", 0.05)
        profile = self.ingest.probe(job.input_file)
        if job.layout_override and job.layout_override != StereoFormat.UNKNOWN:
            profile.stereo_format = job.layout_override
            report(f"Using 3D layout override: {job.layout_override.value}", 0.06)

        # Allocate bitrates
        total_kbps = job.target_bitrate_mbps * 1000
        base_kbps = int(total_kbps * job.split_ratio_base)
        dep_kbps = total_kbps - base_kbps

        # Work in a clean temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix="stereoforge_work_"))
        base_264 = temp_dir / "base_left.264"
        manifest_json = temp_dir / "frame_manifest.json"
        dep_264 = temp_dir / "dependent_right.264"
        is_iso = job.output_file.suffix.lower() in (".iso", ".m2ts") or job.output_file.is_dir() or not job.output_file.suffix
        dep_mvc = (temp_dir / "dependent_right.mvc") if is_iso else None

        try:
            # Stage 1: Pass 1 Base View (GPU)
            report(f"Pass 1: Encoding Left Eye ({base_kbps} kbps on GPU)...", 0.10)
            manifest = self.base_encoder.encode(
                profile=profile,
                output_base_264=base_264,
                output_manifest_json=manifest_json,
                bitrate_kbps=base_kbps,
                strict_bluray=job.strict_bluray,
                swap_eyes=job.swap_eyes
            )

            # Stage 2: Pass 2 Dependent View (CPU)
            report(f"Pass 2: Encoding Right Eye ({dep_kbps} kbps on CPU)...", 0.50)
            success = self.dep_encoder.encode(
                profile=profile,
                base_bitstream_path=base_264,
                manifest=manifest,
                output_dependent_264=dep_264,
                output_dependent_mvc=dep_mvc,
                bitrate_kbps=dep_kbps,
                swap_eyes=job.swap_eyes,
                right_file=job.right_file
            )

            if not success:
                report("Error: Pass 2 encoding failed.", 0.75)
                return False

            # Stage 3: Multiplexing
            if is_iso:
                report("Muxing: Generating 3D Blu-ray structure / ISO with tsMuxeR...", 0.85)
                mux_success = self.muxer.mux_3d_bluray(
                    base_video_path=base_264,
                    dependent_mvc_path=dep_mvc,
                    output_dir_or_iso=job.output_file,
                    audio_source_path=job.input_file,
                    fps=str(round(profile.fps, 3))
                )
            else:
                report("Muxing: Packaging 3D stereoscopic Matroska (.mkv) with mkvmerge...", 0.85)
                mux_success = self.muxer.mux_3d_mkv(
                    base_video_path=base_264,
                    dependent_video_path=dep_264,
                    output_mkv_path=job.output_file,
                    audio_source_path=job.input_file,
                    title=job.title
                )

            elapsed = time.time() - start_time
            if mux_success:
                report(f"Finished successfully in {elapsed:.1f} seconds! Output: {job.output_file}", 1.0)
                return True
            else:
                report("Multiplexing stage failed.", 0.95)
                return False

        except Exception as e:
            report(f"Encode failed: {e}", 0.0)
            return False
        finally:
            # Cleanup temp files
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
