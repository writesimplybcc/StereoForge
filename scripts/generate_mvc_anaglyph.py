"""Generate 3D Anaglyph from Post-MVC Encoded Frames.

Takes raw stereoscopic input from Clips/, runs the complete StereoForge MVC encoding
pipeline (Pass 1 Base View + Pass 2 MVC Dependent View), decodes the actual compressed
bitstreams (post-quantization / inter-view predicted frames), and merges them into a
Dubois Red/Cyan 3D Anaglyph video.
"""

import sys
import time
import subprocess
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from stereoforge.pipeline.ingest import IngestionEngine, StereoFormat
from stereoforge.pipeline.pass1_base import BaseViewEncoder
from stereoforge.pipeline.pass2_dependent import DependentViewEncoder


def main():
    clip_path = Path(r"E:\StereoForge\Clips\Hotel Transylvania 2 3D Trailer Top & Bottom (TAB) 4K.mkv")
    if not clip_path.exists():
        print(f"Error: Input clip not found: {clip_path}")
        return 1

    output_dir = Path(r"E:\StereoForge\Output")
    output_dir.mkdir(parents=True, exist_ok=True)

    anaglyph_mp4 = output_dir / "Hotel_Transylvania_2_MVC_Processed_Anaglyph.mp4"
    sample_png = output_dir / "Hotel_Transylvania_2_MVC_Processed_Anaglyph_sample.png"

    temp_dir = output_dir / "temp_anaglyph_mvc"
    temp_dir.mkdir(parents=True, exist_ok=True)

    base_264 = temp_dir / "left.264"
    dep_264 = temp_dir / "dependent.264"
    dep_mvc = temp_dir / "dependent.mvc"

    print("=" * 75)
    print("👓 STEREOFORGE: GENERATE 3D ANAGLYPH FROM POST-MVC ENCODED FRAMES")
    print("=" * 75)
    print(f"📁 Source Media:      {clip_path.name}")
    print(f"📦 Target Anaglyph:   {anaglyph_mp4}")
    print("ℹ️ Note: Frames are decoded strictly from the compressed MVC bitstreams,")
    print("        NOT from raw uncompressed source video.")
    print("=" * 75)

    ingest = IngestionEngine()
    profile = ingest.probe(clip_path)
    print(f"Detected Format: {profile.stereo_format.name} ({profile.width}x{profile.height} @ {profile.fps:.3f} fps)")

    manifest_json = temp_dir / "frame_manifest.json"

    # 1. Pass 1: Encode Base View (Left Eye) -> left.264
    print("\n[Step 1/4] 🚀 Encoding Pass 1 Base View (Left Eye) with hardware acceleration...")
    base_encoder = BaseViewEncoder()
    manifest = base_encoder.encode(
        profile=profile,
        output_base_264=base_264,
        output_manifest_json=manifest_json,
        bitrate_kbps=18000,
        strict_bluray=False,
        swap_eyes=False
    )
    if not manifest or not base_264.exists():
        print("❌ Pass 1 failed.")
        return 1
    print(f"   Base View bitstream: {base_264} ({base_264.stat().st_size / (1024*1024):.2f} MB)")

    # 2. Pass 2: Encode Dependent View (Right Eye) slaved to manifest -> dependent.264 & dependent.mvc
    print("\n[Step 2/4] ⚡ Encoding Pass 2 MVC Dependent View (Right Eye)...")
    dep_encoder = DependentViewEncoder()
    ok = dep_encoder.encode(
        profile=profile,
        base_bitstream_path=base_264,
        manifest=manifest,
        output_dependent_264=dep_264,
        output_dependent_mvc=dep_mvc,
        bitrate_kbps=10000,
        strict_bluray=False,
        swap_eyes=False,
        use_native_mvc=False
    )
    if not ok or not dep_264.exists():
        print("❌ Pass 2 failed.")
        return 1
    print(f"   Dependent View bitstream: {dep_264} ({dep_264.stat().st_size / (1024*1024):.2f} MB)")

    # 3. Step 3: Decode both post-MVC bitstreams and combine into Dubois Red/Cyan Anaglyph
    print("\n[Step 3/4] 🎨 Decoding post-MVC bitstreams and generating Dubois Red/Cyan Anaglyph...")
    print("   Input 0: left.264 (Decoded Base View)")
    print("   Input 1: dependent.264 (Decoded Dependent MVC View)")

    # Filter: Scale both streams to standard 1080p 1:1 SAR, hstack, and merge with Dubois stereo3d
    # Enforces strict 16:9 square pixels (SAR 1:1) so playback is never squeezed in any player.
    filter_complex = (
        "[0:v]scale=1920:1080,setsar=1[l];"
        "[1:v]scale=1920:1080,setsar=1[r];"
        "[l][r]hstack[sbs];"
        "[sbs]stereo3d=in=sbsl:out=arcd,scale=1920:1080,setsar=1[v_out]"
    )

    cmd_anaglyph = [
        "ffmpeg", "-y",
        "-r", str(round(profile.fps, 3)),
        "-i", str(base_264),
        "-r", str(round(profile.fps, 3)),
        "-i", str(dep_264),
        "-i", str(clip_path),  # For audio track
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", "2:a:0?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-aspect", "16:9",
        "-c:a", "aac",
        "-b:a", "192k",
        str(anaglyph_mp4)
    ]

    print(f"   Running FFmpeg Dubois Anaglyph rendering...")
    t0 = time.time()
    res = subprocess.run(cmd_anaglyph, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"❌ Anaglyph generation failed: {res.stderr}")
        return 1
    print(f"   Anaglyph video created in {time.time() - t0:.1f}s: {anaglyph_mp4} ({anaglyph_mp4.stat().st_size / (1024*1024):.2f} MB)")

    # 4. Step 4: Extract sample screenshot for immediate viewing
    print("\n[Step 4/4] 📸 Extracting sample anaglyph frame at 00:00:15...")
    cmd_ss = [
        "ffmpeg", "-y",
        "-ss", "15",
        "-i", str(anaglyph_mp4),
        "-vframes", "1",
        str(sample_png)
    ]
    subprocess.run(cmd_ss, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Cleanup temp streams
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n" + "=" * 75)
    print("🎉 3D ANAGLYPH GENERATION COMPLETE!")
    print(f"   🎥 Output Video: {anaglyph_mp4}")
    print(f"   🖼️ Sample Image: {sample_png}")
    print("   Wear standard Red/Cyan 3D glasses to view depth!")
    print("=" * 75)
    return 0


if __name__ == "__main__":
    sys.exit(main())
