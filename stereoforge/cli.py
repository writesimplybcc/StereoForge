"""StereoForge Command Line Interface (CLI)."""

import argparse
import sys
from pathlib import Path
from typing import List, Set

from stereoforge import __version__
from stereoforge.pipeline.ingest import IngestionEngine, StereoFormat, find_matching_eye_file
from stereoforge.pipeline.orchestrator import StereoForgePipeline, EncodeJob, BatchProgress, JobResult


def scan_batch_jobs(
    batch_dir: Path,
    output_dir: Path,
    output_format: str = "mkv",
    bitrate: int = 35,
    strict_bluray: bool = False,
    swap_eyes: bool = False,
    auto_detect_inverted_eyes: bool = True,
    engine_mode: str = "native_mvc"
) -> List[EncodeJob]:
    """Scans a directory for 3D video files and constructs EncodeJobs, auto-pairing dual files."""
    valid_extensions = {".mp4", ".mkv", ".mov", ".avi", ".mts", ".m2ts", ".ts"}
    files = sorted([p for p in batch_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_extensions])

    jobs: List[EncodeJob] = []
    processed_paths: Set[Path] = set()

    for p in files:
        if p in processed_paths:
            continue
        # Skip previously encoded 3D outputs
        if p.stem.endswith("_3D"):
            continue

        matched_right = find_matching_eye_file(p)
        if matched_right and matched_right in files and matched_right != p:
            # Pair found
            processed_paths.add(p)
            processed_paths.add(matched_right)
            stem = p.stem.replace("_left", "").replace("_Left", "").replace("_L", "")
            ext = f".{output_format.lstrip('.')}"
            out_file = output_dir / f"{stem}_3D{ext}"
            jobs.append(EncodeJob(
                input_file=p,
                output_file=out_file,
                right_file=matched_right,
                target_bitrate_mbps=bitrate,
                strict_bluray=strict_bluray,
                swap_eyes=swap_eyes,
                layout_override=StereoFormat.DUAL_FILES,
                auto_detect_inverted_eyes=auto_detect_inverted_eyes,
                engine_mode=engine_mode
            ))
        else:
            # Check if this file is a solitary right eye file whose left partner is missing
            name_lower = p.name.lower()
            if any(k in name_lower for k in ["_right", "-right", ".right", "_r.", "-r."]):
                # Skip orphan right eye unless explicitly processed
                continue

            processed_paths.add(p)
            ext = f".{output_format.lstrip('.')}"
            out_file = output_dir / f"{p.stem}_3D{ext}"
            jobs.append(EncodeJob(
                input_file=p,
                output_file=out_file,
                right_file=None,
                target_bitrate_mbps=bitrate,
                strict_bluray=strict_bluray,
                swap_eyes=swap_eyes,
                auto_detect_inverted_eyes=auto_detect_inverted_eyes,
                engine_mode=engine_mode
            ))

    return jobs


def main():
    parser = argparse.ArgumentParser(
        prog="stereoforge",
        description="StereoForge: High-Performance Stereoscopic 3D MVC Video Encoder & Packager.\nImagined by writesimply.bcc • Coded by Gemini"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Single File Inputs
    parser.add_argument("-i", "--input", type=Path, help="Input 3D video file (SBS, TAB, or Left Eye)")
    parser.add_argument("--right", type=Path, help="Optional separate Right Eye input file for dual-file workflows")
    parser.add_argument("-o", "--output", type=Path, help="Output destination (.mkv or .iso)")

    # Batch Inputs
    parser.add_argument("-b", "--batch-dir", type=Path, help="Directory containing multiple 3D videos to process in batch")
    parser.add_argument("--output-dir", type=Path, help="Destination directory for batch processing outputs")
    parser.add_argument(
        "--format",
        choices=["mkv", "iso"],
        default="mkv",
        help="Output container format for batch encoding (default: mkv)"
    )

    # Encoding Options
    parser.add_argument("--bitrate", type=int, default=35, help="Combined target bitrate in Mbps (default: 35)")
    parser.add_argument("--preset", choices=["bd50", "bd25", "vr", "custom"], default="vr", help="Quality profile preset")
    parser.add_argument("--swap-eyes", action="store_true", help="Force swap Left and Right eye channels")
    parser.add_argument("--check-parity", action="store_true", default=True, help="Run automated inverted eye disparity check (default: True)")
    parser.add_argument("--no-check-parity", dest="check_parity", action="store_false", help="Disable automated inverted eye check")
    parser.add_argument(
        "--engine",
        choices=["native_mvc", "gpu_turbo"],
        default="native_mvc",
        help="Encoding engine mode: 'native_mvc' (default: True space-saving MVC inter-view injection) or 'gpu_turbo' (fast GPU simulcast)"
    )
    parser.add_argument("--title", type=str, help="Optional container title metadata")
    parser.add_argument("--strict-bluray", action="store_true", help="Enforce physical Blu-ray VBV buffer limits (max 40 Mbps)")
    parser.add_argument("--dry-run", action="store_true", help="Probe and display planned encode jobs without executing")

    args = parser.parse_args()

    print(f"🎬 StereoForge v{__version__}")
    print("   Imagined by writesimply.bcc • Coded by Gemini\n")

    strict_bd = args.strict_bluray or (args.preset in ("bd50", "bd25"))
    effective_bitrate = args.bitrate
    if args.preset == "bd50":
        effective_bitrate = 40
    elif args.preset == "bd25":
        effective_bitrate = 23
    elif args.preset == "vr" and args.bitrate == 35:
        effective_bitrate = 20

    # ---------------------------------------------------------
    # BATCH MODE
    # ---------------------------------------------------------
    if args.batch_dir:
        if not args.batch_dir.exists() or not args.batch_dir.is_dir():
            print(f"❌ Error: Batch directory does not exist: {args.batch_dir}")
            return 1
        output_dir = args.output_dir or args.batch_dir / "StereoForge_Output"
        output_dir.mkdir(parents=True, exist_ok=True)

        jobs = scan_batch_jobs(
            batch_dir=args.batch_dir,
            output_dir=output_dir,
            output_format=args.format,
            bitrate=effective_bitrate,
            strict_bluray=strict_bd,
            swap_eyes=args.swap_eyes,
            auto_detect_inverted_eyes=args.check_parity,
            engine_mode=args.engine
        )

        if not jobs:
            print(f"⚠️ No 3D video files found in batch directory: {args.batch_dir}")
            return 0

        print(f"📋 Found {len(jobs)} 3D encode jobs in batch queue:")
        for idx, j in enumerate(jobs, 1):
            pair_note = f" + [Right: {j.right_file.name}]" if j.right_file else ""
            print(f"   [{idx:02d}] {j.input_file.name}{pair_note} -> {j.output_file.name} ({j.target_bitrate_mbps} Mbps, {j.engine_mode})")

        if args.dry_run:
            print("\n🔍 Dry-run mode enabled. Exiting without encoding.")
            return 0

        print(f"\n🚀 Starting batch queue execution ({len(jobs)} items)...")
        pipeline = StereoForgePipeline()

        def on_batch_progress(prog: BatchProgress):
            pass

        results = pipeline.run_batch(jobs, batch_progress_cb=on_batch_progress)

        print("\n================== 📊 BATCH EXECUTION SUMMARY ==================")
        success_cnt = sum(1 for r in results if r.success)
        fail_cnt = sum(1 for r in results if not r.success)
        for idx, r in enumerate(results, 1):
            st = "✅ SUCCESS" if r.success else f"❌ FAILED ({r.error})"
            sz_mb = r.output_size_bytes / (1024 * 1024)
            print(f"  [{idx:02d}] {st}: {r.job.output_file.name} ({sz_mb:.1f} MB in {r.elapsed_seconds:.1f}s)")
        print(f"\nTotal: {len(results)} jobs | Passed: {success_cnt} | Failed: {fail_cnt}")
        print("================================================================\n")
        return 0 if fail_cnt == 0 else 1

    # ---------------------------------------------------------
    # SINGLE FILE MODE
    # ---------------------------------------------------------
    if not args.input:
        parser.print_help()
        print("\n❌ Error: Please specify either --input (-i) for single file mode or --batch-dir (-b) for batch mode.")
        return 1

    if not args.input.exists():
        print(f"❌ Error: Input file does not exist: {args.input}")
        return 1

    engine = IngestionEngine()
    profile = engine.probe(args.input)

    output_path = args.output
    if not output_path:
        ext = ".iso" if args.format == "iso" else ".mkv"
        output_path = args.input.with_name(f"{args.input.stem}_3D{ext}")

    print(f"📁 Ingesting: {args.input.name}")
    print(f"   Detected format: {profile.stereo_format.value}")
    print(f"   Resolution: {profile.width}x{profile.height} @ {profile.fps:.3f} fps")
    print(f"   Color profile: 10-bit={profile.is_10bit}, HDR={profile.is_hdr}")
    print(f"   Audio Streams: {len(profile.audio_streams)} track(s) detected")
    for a in profile.audio_streams:
        print(f"     - Track {a.get('audio_index', 0)}: {a.get('codec', 'unknown').upper()} ({a.get('channels', 2)} ch, {a.get('language', 'und')})")

    is_iso = output_path.suffix.lower() == ".iso"
    if is_iso and not (23.97 <= profile.fps <= 24.01):
        print(f"ℹ️ Reminder: Source is {profile.fps:.2f} fps. Physical 3D Blu-ray video discs for standalone consumer players strictly require 1080p @ 23.976 fps. For VLC4MVC, Android players, or network streaming, {profile.fps:.2f} fps will play normally.")

    job = EncodeJob(
        input_file=args.input,
        output_file=output_path,
        right_file=args.right,
        target_bitrate_mbps=effective_bitrate,
        strict_bluray=strict_bd,
        swap_eyes=args.swap_eyes,
        title=args.title,
        auto_detect_inverted_eyes=args.check_parity,
        engine_mode=args.engine
    )

    if args.dry_run:
        print("\n🔍 Dry-run mode enabled. Exiting without encoding.")
        return 0

    print(f"\n🚀 Starting encode: {job.input_file.name} -> {job.output_file.name}")
    print(f"   Engine: {job.engine_mode} | Bitrate: {job.target_bitrate_mbps} Mbps\n")

    pipeline = StereoForgePipeline()
    success = pipeline.run(job)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
