"""Unit tests for StereoForge pure python modules (Manifest, MVC Syntax, Ingestion)."""

import tempfile
from pathlib import Path

from stereoforge.core.manifest import FrameManifest, StreamMetadata, FrameEntry
from stereoforge.core.mvc_syntax import MVCViewInfo, MVCBitstreamHeader
from stereoforge.pipeline.ingest import MediaProfile, StereoFormat, IngestionEngine


def test_frame_manifest_serialization():
    meta = StreamMetadata(1920, 1080, 24000, 1001)
    manifest = FrameManifest(metadata=meta)

    manifest.add_frame(FrameEntry(index=0, slice_type="IDR", pts=0, dts=0, poc=0, is_keyframe=True))
    manifest.add_frame(FrameEntry(index=1, slice_type="B", pts=2, dts=1, poc=2))
    manifest.add_frame(FrameEntry(index=2, slice_type="P", pts=1, dts=2, poc=1))

    summary = manifest.summary()
    assert summary["total_frames"] == 3
    assert summary["idr_frames"] == 1
    assert summary["b_frames"] == 1
    assert summary["p_frames"] == 1

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        manifest.save(tmp_path)
        loaded = FrameManifest.load(tmp_path)
        assert len(loaded.frames) == 3
        assert loaded.frames[0].slice_type == "IDR"
        assert loaded.frames[1].slice_type == "B"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_mvc_nal_header_packing():
    # Test Dependent View (Right Eye, view_id = 1)
    view = MVCViewInfo(view_id=1, is_base_view=False, inter_view_flag=True, anchor_pic_flag=False)
    packed = MVCBitstreamHeader.pack_nal_header_extension(view, non_idr_flag=True)

    assert len(packed) == 3
    unpacked = MVCBitstreamHeader.unpack_nal_header_extension(packed)

    assert unpacked.view_id == 1
    assert not unpacked.is_base_view
    assert unpacked.inter_view_flag is True
    assert unpacked.anchor_pic_flag is False


def test_ingest_filter_generation():
    profile = MediaProfile(
        path=Path("dummy.mp4"),
        width=3840,
        height=1080,
        fps=23.976,
        fps_str="24000/1001",
        duration=100.0,
        codec="h264",
        pix_fmt="yuv420p",
        is_10bit=False,
        is_hdr=False,
        stereo_format=StereoFormat.FULL_SBS,
        audio_tracks=1,
        subtitle_tracks=0
    )

    l_chain, r_chain = IngestionEngine.get_filter_chains(profile, swap_eyes=False)
    assert "crop=iw/2:ih:0:0" in l_chain
    assert "crop=iw/2:ih:iw/2:0" in r_chain

    # Test 4K SBS and 4K TAB scaling to 1080p
    profile_4k_sbs = MediaProfile(
        path=Path("movie_4k_sbs.mp4"),
        width=3840,
        height=2160,
        fps=23.976,
        fps_str="24000/1001",
        duration=100.0,
        codec="h264",
        pix_fmt="yuv420p",
        is_10bit=False,
        is_hdr=False,
        stereo_format=StereoFormat.HALF_SBS,
        audio_tracks=1,
        subtitle_tracks=0
    )
    l_4k_sbs, r_4k_sbs = IngestionEngine.get_filter_chains(profile_4k_sbs)
    assert "scale=1920:1080" in l_4k_sbs
    assert "scale=1920:1080" in r_4k_sbs

    profile_4k_tab = MediaProfile(
        path=Path("movie_4k_tab.mp4"),
        width=3840,
        height=2160,
        fps=23.976,
        fps_str="24000/1001",
        duration=100.0,
        codec="h264",
        pix_fmt="yuv420p",
        is_10bit=False,
        is_hdr=False,
        stereo_format=StereoFormat.HALF_TAB,
        audio_tracks=1,
        subtitle_tracks=0
    )
    l_4k_tab, r_4k_tab = IngestionEngine.get_filter_chains(profile_4k_tab)
    assert "crop=iw:ih/2:0:0" in l_4k_tab
    assert "crop=iw:ih/2:0:ih/2" in r_4k_tab
    assert "scale=1920:1080" in l_4k_tab
    assert "scale=1920:1080" in r_4k_tab


def test_interleave_mvc_streams():
    from stereoforge.pipeline.muxer import interleave_mvc_streams

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        base = tmp_path / "base.264"
        dep = tmp_path / "dep.264"
        out = tmp_path / "out.264"

        # Construct dummy Annex B NALs
        # Base: SPS (7), PPS (8), Slice (1)
        base.write_bytes(
            b"\x00\x00\x00\x01\x67\x42\x00\x1e"  # SPS
            b"\x00\x00\x00\x01\x68\xce\x3c\x80"  # PPS
            b"\x00\x00\x00\x01\x21\x9a\x01"      # Slice 1
            b"\x00\x00\x00\x01\x21\x9a\x02"      # Slice 2
        )
        # Dep: Slice Ext (20)
        dep.write_bytes(
            b"\x00\x00\x00\x01\x34\x01\x02\x03\x9b\x01"  # MVC Slice 1
            b"\x00\x00\x00\x01\x34\x01\x02\x03\x9b\x02"  # MVC Slice 2
        )

        interleave_mvc_streams(base, dep, out)
        assert out.exists()
        out_bytes = out.read_bytes()
        # Verify SPS and PPS appear at the start, and slices are interleaved
        assert b"\x67\x42" in out_bytes
        assert b"\x68\xce" in out_bytes
        assert b"\x34\x01\x02\x03\x9b\x01" in out_bytes


def test_encode_job_title_optional():
    from stereoforge.pipeline.orchestrator import EncodeJob
    job_default = EncodeJob(input_file=Path("in.mp4"), output_file=Path("out.mkv"))
    assert job_default.title is None

    job_custom = EncodeJob(input_file=Path("in.mp4"), output_file=Path("out.mkv"), title="My Custom 3D Feature")
    assert job_custom.title == "My Custom 3D Feature"


def test_dual_files_matching():
    from stereoforge.pipeline.ingest import find_matching_eye_file

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        left = tmp_path / "MyFeature_Left.mp4"
        right = tmp_path / "MyFeature_Right.mp4"
        left.write_text("left")
        right.write_text("right")

        matched = find_matching_eye_file(left)
        assert matched is not None
        assert matched.name == "MyFeature_Right.mp4"


def test_anaglyph_filter_generation():
    from stereoforge.ui.preview import get_anaglyph_filter_config
    from stereoforge.pipeline.ingest import StereoFormat

    f_sbs, is_c = get_anaglyph_filter_config(StereoFormat.HALF_SBS, swap_eyes=False)
    assert not is_c
    assert "stereo3d=sbs2l:arcd" in f_sbs

    f_sbs_swap, _ = get_anaglyph_filter_config(StereoFormat.HALF_SBS, swap_eyes=True)
    assert "stereo3d=sbs2r:arcd" in f_sbs_swap

    f_tab, _ = get_anaglyph_filter_config(StereoFormat.HALF_TAB, swap_eyes=False)
    assert "stereo3d=ab2l:arcd" in f_tab

    f_dual, is_c2 = get_anaglyph_filter_config(StereoFormat.DUAL_FILES, swap_eyes=False, is_dual=True)
    assert is_c2
    assert "hstack" in f_dual


if __name__ == "__main__":
    test_frame_manifest_serialization()
    test_mvc_nal_header_packing()
    test_ingest_filter_generation()
    test_interleave_mvc_streams()
    test_encode_job_title_optional()
    test_dual_files_matching()
    test_anaglyph_filter_generation()
    print("ALL PURE PYTHON TESTS PASSED!")
