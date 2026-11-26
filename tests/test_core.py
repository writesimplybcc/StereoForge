"""Unit tests for StereoForge core modules."""

import tempfile
from pathlib import Path
import numpy as np

from stereoforge.core.manifest import FrameManifest, StreamMetadata, FrameEntry
from stereoforge.core.mvc_syntax import MVCViewInfo, MVCBitstreamHeader
from stereoforge.core.disparity import render_dubois_anaglyph, render_simple_anaglyph, detect_inverted_eyes
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


def test_dubois_anaglyph_rendering():
    h, w = 120, 160
    left = np.full((h, w, 3), 200, dtype=np.uint8)
    right = np.full((h, w, 3), 100, dtype=np.uint8)

    anaglyph = render_dubois_anaglyph(left, right)
    assert anaglyph.shape == (h, w, 3)
    assert anaglyph.dtype == np.uint8

    simple = render_simple_anaglyph(left, right)
    assert simple.shape == (h, w, 3)
    assert simple[0, 0, 0] == 200  # Red from Left
    assert simple[0, 0, 1] == 100  # Green from Right


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

    # Test swap eyes
    l_swapped, r_swapped = IngestionEngine.get_filter_chains(profile, swap_eyes=True)
    assert "crop=iw/2:ih:iw/2:0" in l_swapped
    assert "crop=iw/2:ih:0:0" in r_swapped
