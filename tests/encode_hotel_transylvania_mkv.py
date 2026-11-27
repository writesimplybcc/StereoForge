"""Full End-to-End Pipeline Encode: Hotel Transylvania 2 -> 3D Matroska (.mkv).

Uses:
- Pass 1: Hardware GPU acceleration (Intel QSV)
- Pass 2: True MVC Inter-View Reference Injection (stereoforge-core)
- Multiplexer: mkvmerge interleaving access units (Base AVC + Dependent MVC) with original audio
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
    output_mkv = Path(r"E:\StereoForge\Output\Hotel_Transylvania_2_3D.mkv")

    if not clip_path.exists():
        print(f"Error: {clip_path} not found.")
        return 1

    print("=" * 70)
    print("🎬 STEREOFORGE END-TO-END PIPELINE: HOTEL TRANSYLVANIA 2 -> 3D MVC MKV")
    print("=" * 70)
    print(f"📁 Input Media:  {clip_path.name}")
    print(f"📦 Output MKV:   {output_mkv}")

    job = EncodeJob(
        input_file=clip_path,
        output_file=output_mkv,
        target_bitrate_mbps=28,
        strict_bluray=False,
        swap_eyes=False,
        title="Hotel Transylvania 2 3D (True MVC)",
        auto_detect_inverted_eyes=True,
        engine_mode="native_mvc"
    )

    pipeline = StereoForgePipeline()
    start_t = time.time()
    success = pipeline.run(job)
    elapsed = time.time() - start_t

    if success and output_mkv.exists():
        size_mb = output_mkv.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 70)
        print(f"🎉 3D MVC MKV ENCODED SUCCESSFULLY IN {elapsed:.1f}s!")
        print(f"   MKV File: {output_mkv}")
        print(f"   Size:     {size_mb:.2f} MB ({output_mkv.stat().st_size:,} bytes)")
        print("   Ready for VLC4MVC, Quest, Vision Pro, 4XVR, or 2D players!")
        print("=" * 70)
        return 0
    else:
        print("\n❌ Pipeline failed to author 3D MVC MKV.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
