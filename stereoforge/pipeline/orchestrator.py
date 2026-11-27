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
    auto_detect_inverted_eyes: bool = False
    engine_mode: str = "native_mvc"  # "native_mvc" (default) or "gpu_turbo"


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

        if job.auto_detect_inverted_eyes:
            report("Analyzing stereoscopic orientation across video...", 0.065)
            dur = profile.duration if profile.duration > 0 else 60.0
            test_points = [dur * 0.25, dur * 0.50, dur * 0.75]
            inverted_votes = 0
            valid_samples = 0
            for tp in test_points:
                l_img, r_img = self.ingest.extract_stereo_pair(
                    profile=profile,
                    timestamp_sec=tp,
                    target_w=640,
                    target_h=360,
                    swap_eyes=job.swap_eyes,
                    right_file=job.right_file
                )
                if l_img is not None and r_img is not None:
                    from stereoforge.core.disparity import detect_inverted_eyes
                    res = detect_inverted_eyes(l_img, r_img)
                    if res.get("confidence", 0.0) >= 0.5:
                        valid_samples += 1
                        if res.get("is_inverted", False):
                            inverted_votes += 1

            if valid_samples > 0 and inverted_votes > (valid_samples / 2):
                report(f"⚠️ Pseudoscopic (inverted eyes) detected ({inverted_votes}/{valid_samples} samples)! Auto-correcting Left/Right channels.", 0.07)
                job.swap_eyes = not job.swap_eyes
            else:
                report("Stereoscopic eye orientation verified: Standard Left/Right.", 0.07)

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
        dep_mvc = (temp_dir / "dependent_right.mvc") if (is_iso or job.engine_mode == "native_mvc") else None

        if is_iso and not (23.97 <= profile.fps <= 24.01):
            report(
                f"ℹ️ Reminder: Source is {profile.fps:.2f} fps. Physical 3D Blu-ray video discs for standalone consumer players strictly require 1080p @ 23.976 fps. For VLC4MVC, Android players, or network streaming, {profile.fps:.2f} fps will play normally.",
                0.07
            )

        try:
            # Stage 1: Pass 1 Base View (GPU)
            report(f"Pass 1: Encoding Left Eye ({base_kbps} kbps on {self.base_encoder.encoder})...", 0.10)
            manifest = self.base_encoder.encode(
                profile=profile,
                output_base_264=base_264,
                output_manifest_json=manifest_json,
                bitrate_kbps=base_kbps,
                strict_bluray=job.strict_bluray,
                swap_eyes=job.swap_eyes
            )

            # Stage 2: Pass 2 Dependent View
            enc_desc = "native stereoforge-core (True MVC)" if job.engine_mode == "native_mvc" else self.dep_encoder.encoder
            report(f"Pass 2: Encoding Right Eye ({dep_kbps} kbps on {enc_desc})...", 0.50)
            success = self.dep_encoder.encode(
                profile=profile,
                base_bitstream_path=base_264,
                manifest=manifest,
                output_dependent_264=dep_264,
                output_dependent_mvc=dep_mvc,
                bitrate_kbps=dep_kbps,
                strict_bluray=job.strict_bluray,
                swap_eyes=job.swap_eyes,
                right_file=job.right_file,
                use_native_mvc=(job.engine_mode == "native_mvc")
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
                if job.engine_mode == "native_mvc" and dep_mvc and dep_mvc.exists():
                    from stereoforge.pipeline.muxer import interleave_mvc_streams, find_mkvmerge
                    interleaved_264 = temp_dir / "interleaved_mvc.264"
                    interleave_mvc_streams(base_264, dep_mvc, interleaved_264)
                    mkvmerge_bin = find_mkvmerge()
                    cmd_mkv = [mkvmerge_bin, "-o", str(job.output_file)]
                    if job.title:
                        cmd_mkv.extend(["--title", job.title])
                    fps_str = str(round(profile.fps, 3))
                    cmd_mkv.extend([
                        "--default-duration", f"0:{fps_str}fps",
                        "--track-name", "0:3D MVC Video (Left 2D Base + Right MVC)",
                        "--display-dimensions", "0:1920x1080",
                        str(interleaved_264)
                    ])
                    if job.input_file and job.input_file.exists():
                        cmd_mkv.extend(["-D", str(job.input_file)])
                    try:
                        import subprocess
                        res = subprocess.run(cmd_mkv, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        mux_success = True
                    except Exception as e:
                        print(f"[StereoForge] Interleaved MKV muxing failed ({e}), falling back to standard dual-track...")
                        mux_success = self.muxer.mux_3d_mkv(
                            base_video_path=base_264,
                            dependent_video_path=dep_264 if dep_264.exists() else dep_mvc,
                            output_mkv_path=job.output_file,
                            audio_source_path=job.input_file,
                            title=job.title,
                            fps=str(round(profile.fps, 3))
                        )
                else:
                    mux_success = self.muxer.mux_3d_mkv(
                        base_video_path=base_264,
                        dependent_video_path=dep_264,
                        output_mkv_path=job.output_file,
                        audio_source_path=job.input_file,
                        title=job.title,
                        fps=str(round(profile.fps, 3))
                    )

            elapsed = time.time() - start_time
            if mux_success:
                base_sz = base_264.stat().st_size if base_264.exists() else 0
                dep_sz = 0
                if dep_mvc and dep_mvc.exists():
                    dep_sz = dep_mvc.stat().st_size
                elif dep_264 and dep_264.exists():
                    dep_sz = dep_264.stat().st_size
                out_sz = job.output_file.stat().st_size if job.output_file.exists() else 0

                dur = profile.duration if profile.duration > 0 else 1.0
                base_mb = base_sz / (1024 * 1024)
                dep_mb = dep_sz / (1024 * 1024)
                out_mb = out_sz / (1024 * 1024)
                base_mbps = (base_sz * 8) / (dur * 1000 * 1000)
                dep_mbps = (dep_sz * 8) / (dur * 1000 * 1000)
                dep_ratio = (dep_sz / base_sz * 100.0) if base_sz > 0 else 0.0

                report("------------------- 📊 STEREOFORGE DATA BREAKDOWN -------------------", 0.98)
                report(f"  👁️  Left Eye  (Base 2D View):     {base_mb:6.2f} MB  ({base_mbps:5.2f} Mbps)", 0.985)
                report(f"  👁️  Right Eye (Dependent MVC):    {dep_mb:6.2f} MB  ({dep_mbps:5.2f} Mbps | {dep_ratio:.1f}% of base)", 0.99)
                if dep_ratio < 70.0:
                    savings = (1.0 - dep_sz / base_sz) * 100.0
                    report(f"  ✨ True MVC Inter-View Savings:   {savings:.1f}% space saved on Dependent View!", 0.995)
                report(f"  📦 Finished Output ({job.output_file.suffix}):   {out_mb:6.2f} MB", 0.998)
                report("---------------------------------------------------------------------", 0.999)
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
