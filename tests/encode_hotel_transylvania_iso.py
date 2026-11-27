"""Full End-to-End Pipeline Encode: Hotel Transylvania 2 -> 3D Blu-ray ISO.

Uses:
- Pass 1: Hardware GPU acceleration (Intel QSV)
- Pass 2: True MVC Inter-View Reference Injection (stereoforge-core)
- Multiplexer: tsMuxeR authoring bootable 3D Blu-ray ISO with AC-3 5.1/Stereo audio
"""

import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from stereoforge.pipeline.orchestrator import StereoForgePipeline, EncodeJob


def main():
    clip_path = Path(r"E:\StereoForge\Clips\Hotel Transylvania 2 3D Trailer Top & Bottom (TAB) 4K.mkv")
    output_iso = Path(r"E:\StereoForge\Output\Hotel_Transylvania_2_3D.iso")

    if not clip_path.exists():
        print(f"Error: {clip_path} not found.")
        return 1

    print("=" * 70)
    print("🎬 STEREOFORGE END-TO-END PIPELINE: HOTEL TRANSYLVANIA 2 -> 3D BLU-RAY ISO")
    print("=" * 70)
    print(f"📁 Input Media:  {clip_path.name}")
    print(f"💿 Output ISO:   {output_iso}")

    job = EncodeJob(
        input_file=clip_path,
        output_file=output_iso,
        target_bitrate_mbps=28,
        strict_bluray=True,
        swap_eyes=False,
        title="Hotel Transylvania 2 3D",
        auto_detect_inverted_eyes=True,
        engine_mode="native_mvc"
    )

    pipeline = StereoForgePipeline()
    start_t = time.time()
    success = pipeline.run(job)
    elapsed = time.time() - start_t

    if success and output_iso.exists():
        size_mb = output_iso.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 70)
        print(f"🎉 3D BLU-RAY ISO ENCODED SUCCESSFULLY IN {elapsed:.1f}s!")
        print(f"   ISO File: {output_iso}")
        print(f"   Size:     {size_mb:.2f} MB ({output_iso.stat().st_size:,} bytes)")
        print("   Ready for VLC4MVC playback on 3D 4K projector or physical disc burning!")
        print("=" * 70)
        return 0
    else:
        print("\n❌ Pipeline failed to author 3D Blu-ray ISO.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
