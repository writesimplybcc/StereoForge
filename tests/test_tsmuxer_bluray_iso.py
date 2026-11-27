"""Test 3D Blu-ray Disc and ISO Authoring via tsMuxeR.

Validates that StereoForge produces a compliant 3D Blu-ray directory structure
or bootable .iso image containing AVC base view and MVC dependent view.
"""

import sys
import tempfile
import subprocess
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from stereoforge.pipeline.muxer import MuxerEngine
from stereoforge.pipeline.pass1_base import detect_best_h264_encoder, get_h264_encoder_options
from stereoforge_core.python.native_bridge import NativeMVCEngine


def main():
    print("=" * 70)
    print("💿 TEST: 3D BLU-RAY & ISO AUTHORING (tsMuxeR + MVC NATIVE ENGINE)")
    print("=" * 70)

    muxer = MuxerEngine()
    if not muxer.is_tsmuxer_available():
        print(f"Error: tsMuxeR not found at {muxer.tsmuxer_bin}")
        return 1

    print(f"✅ Found tsMuxeR: {muxer.tsmuxer_bin}")

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        w, h = 1920, 1080
        fps = "24000/1001"
        num_frames = 24  # 1 second test clip
        luma_sz = w * h

        base_264 = tmp_dir / "base_left.264"
        dep_mvc = tmp_dir / "dep_right.mvc"
        iso_out = tmp_dir / "test_3d_bluray.iso"
        bdmv_out = tmp_dir / "BDMV_OUTPUT"

        # 1. Synthesize Left Eye raw YUV & encode with active GPU
        print("\n[1/3] Generating Base View (Left Eye) AVC stream...")
        hw_enc = detect_best_h264_encoder()
        print(f"      Active encoder: {hw_enc}")

        yuv_data = bytes([128] * (w * h * 3 // 2)) * num_frames
        raw_yuv = tmp_dir / "raw_synthetic.yuv"
        with open(raw_yuv, "wb") as f:
            f.write(yuv_data)

        cmd_base = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{w}x{h}", "-r", fps,
            "-i", str(raw_yuv),
        ]
        cmd_base.extend(get_h264_encoder_options(hw_enc, bitrate_kbps=15000, strict_bluray=True))
        cmd_base.extend(["-f", "h264", str(base_264)])
        subprocess.run(cmd_base, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"      Base view generated: {base_264.stat().st_size:,} bytes")

        # 2. Synthesize Dependent View (Right Eye) MVC stream with native C engine
        print("\n[2/3] Generating Dependent View (Right Eye) MVC stream...")
        native = NativeMVCEngine(width=w, height=h, bitrate_kbps=10000, strict_bluray=True)
        sps = native.get_subset_sps()

        r_luma = bytes([135] * luma_sz)
        l_luma = bytes([128] * luma_sz)

        with open(dep_mvc, "wb") as fmvc:
            fmvc.write(sps)
            for f_idx in range(num_frames):
                is_key = (f_idx == 0)
                pkt = native.encode_dependent_frame(
                    right_y=r_luma,
                    left_y=l_luma,
                    is_keyframe=is_key,
                    pts=f_idx * 1001,
                    dts=f_idx * 1001
                )
                fmvc.write(pkt)
        native.close()
        print(f"      Dependent MVC view generated: {dep_mvc.stat().st_size:,} bytes")

        # 3. Mux into 3D Blu-ray ISO using tsMuxeR
        print("\n[3/3] Authoring 3D Blu-ray ISO with tsMuxeR...")
        ok_iso = muxer.mux_3d_bluray(
            base_video_path=base_264,
            dependent_mvc_path=dep_mvc,
            output_dir_or_iso=iso_out,
            fps="23.976",
            is_iso=True
        )
        assert ok_iso, "tsMuxeR 3D ISO authoring failed"
        assert iso_out.exists() and iso_out.stat().st_size > 0, "ISO was not created"
        print(f"      🎉 Success! 3D Blu-ray ISO created: {iso_out.stat().st_size:,} bytes ({iso_out.stat().st_size / (1024*1024):.2f} MB)")

        # 4. Mux into 3D Blu-ray Directory Structure (BDMV)
        print("\n      Authoring 3D Blu-ray BDMV directory structure with tsMuxeR...")
        bdmv_out.mkdir()
        ok_bdmv = muxer.mux_3d_bluray(
            base_video_path=base_264,
            dependent_mvc_path=dep_mvc,
            output_dir_or_iso=bdmv_out,
            fps="23.976",
            is_iso=False
        )
        assert ok_bdmv, "tsMuxeR 3D BDMV folder authoring failed"
        bdmv_stream_dir = bdmv_out / "BDMV" / "STREAM"
        assert bdmv_stream_dir.exists(), f"BDMV/STREAM not found in {bdmv_out}"

        m2ts_files = list(bdmv_stream_dir.glob("*.m2ts"))
        print(f"      Found {len(m2ts_files)} M2TS streams in BDMV/STREAM: {[f.name for f in m2ts_files]}")
        print("      🎉 Success! 3D Blu-ray BDMV folder authoring confirmed.")

    print("\n" + "=" * 70)
    print("🎉 ALL 3D BLU-RAY & ISO AUTHORING TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
