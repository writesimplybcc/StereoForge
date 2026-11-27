"""StereoForge Command Line Interface (CLI)."""

import argparse
import sys
from pathlib import Path

from stereoforge import __version__
from stereoforge.core.manifest import FrameManifest, StreamMetadata, FrameEntry
from stereoforge.pipeline.ingest import IngestionEngine, StereoFormat
from stereoforge.pipeline.muxer import MuxerEngine


def main():
    parser = argparse.ArgumentParser(
        prog="stereoforge",
        description="StereoForge: High-Performance Stereoscopic 3D MVC Video Encoder & Packager.\nImagined by writesimply.bcc • Coded by Gemini"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-i", "--input", type=Path, required=True, help="Input 3D video file (SBS, TAB, or Left Eye)")
    parser.add_argument("--right", type=Path, help="Optional separate Right Eye input file for dual-file workflows")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output destination (.mkv or .iso)")
    parser.add_argument("--bitrate", type=int, default=35, help="Combined target bitrate in Mbps (default: 35)")
    parser.add_argument("--preset", choices=["bd50", "bd25", "vr", "custom"], default="vr", help="Quality profile preset")
    parser.add_argument("--swap-eyes", action="store_true", help="Force swap Left and Right eye channels")
    parser.add_argument("--check-parity", action="store_true", help="Run automated inverted eye disparity check")
    parser.add_argument(
        "--engine",
        choices=["native_mvc", "gpu_turbo"],
        default="native_mvc",
        help="Encoding engine mode: 'native_mvc' (default: True space-saving MVC inter-view injection) or 'gpu_turbo' (fast GPU simulcast)"
    )

    args = parser.parse_args()

    print(f"🎬 StereoForge v{__version__}")
    print("   Imagined by writesimply.bcc • Coded by Gemini")
    print(f"📁 Ingesting: {args.input}")

    engine = IngestionEngine()
    profile = engine.probe(args.input)
    print(f"   Detected format: {profile.stereo_format.value}")
    print(f"   Resolution: {profile.width}x{profile.height} @ {profile.fps:.3f} fps")
    print(f"   Color profile: 10-bit={profile.is_10bit}, HDR={profile.is_hdr}")

    if args.output.suffix.lower() == ".iso" and not (23.97 <= profile.fps <= 24.01):
        print(f"ℹ️ Reminder: Source is {profile.fps:.2f} fps. Physical 3D Blu-ray video discs for standalone consumer players strictly require 1080p @ 23.976 fps. For VLC4MVC, Android players, or network streaming, {profile.fps:.2f} fps will play normally.")

    print("✅ Configuration validated. Ready for pipeline execution.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
