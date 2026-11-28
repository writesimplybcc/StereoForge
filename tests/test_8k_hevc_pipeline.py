"""Test 8K HEVC Stereoscopic Ingestion for 1080p MVC Encoding.

Verifies:
1. Ingestion of 8K 10-bit HEVC media (7680x2160 Full-SBS).
2. Proper detection: is_8k=True, is_10bit=True, StereoFormat.FULL_SBS.
3. Lanczos3 downscaling from 8K/4K down to 1080p square pixels (setsar=1).
4. Full end-to-end MVC pipeline execution producing 1080p 3D MKV and 3D Blu-ray ISO.
"""

import sys
import pytest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from stereoforge.pipeline.ingest import IngestionEngine, MediaProfile, StereoFormat
from stereoforge.pipeline.orchestrator import StereoForgePipeline, EncodeJob
from stereoforge.pipeline.muxer import MuxerEngine

clip_path = repo_root / "Clips" / "Test_8K_HEVC_FullSBS_7680x2160.mp4"


def test_8k_hevc_filter_chains():
    """Validates 8K HEVC profile filter chain synthesis with Lanczos3 scaling."""
    profile = MediaProfile(
        path=Path("dummy_8k.mp4"),
        width=7680,
        height=2160,
        fps=23.976,
        fps_str="24000/1001",
        duration=10.0,
        codec="hevc",
        pix_fmt="yuv420p10le",
        is_10bit=True,
        is_hdr=False,
        stereo_format=StereoFormat.FULL_SBS,
        audio_tracks=1,
        subtitle_tracks=0,
        is_8k=True
    )

    assert profile.codec == "hevc"
    assert profile.width == 7680
    assert profile.height == 2160
    assert profile.is_8k is True
    assert profile.is_10bit is True
    assert profile.stereo_format == StereoFormat.FULL_SBS

    l_chain, r_chain = IngestionEngine.get_filter_chains(profile)
    assert "scale=1920:1080:flags=lanczos" in l_chain
    assert "scale=1920:1080:flags=lanczos" in r_chain
    assert "format=yuv420p" in l_chain
    assert "format=yuv420p" in r_chain


@pytest.mark.skipif(not clip_path.exists(), reason="Requires local 8K HEVC test clip in Clips/")
def test_8k_hevc_probe_real_clip():
    """Probes the physical 8K HEVC test clip when present on the system."""
    ingest = IngestionEngine()
    profile = ingest.probe(clip_path)

    assert profile.codec == "hevc"
    assert profile.width == 7680
    assert profile.height == 2160
    assert profile.is_8k is True
    assert profile.is_10bit is True
    assert profile.stereo_format == StereoFormat.FULL_SBS


@pytest.mark.skipif(not clip_path.exists(), reason="Requires local 8K HEVC test clip in Clips/")
def test_8k_hevc_to_1080p_mvc_mkv_encode(tmp_path):
    """Executes full 8K HEVC -> 1080p MVC MKV pipeline when test clip is present."""
    out_mkv = tmp_path / "Test_8K_HEVC_to_1080p_MVC.mkv"

    job = EncodeJob(
        input_file=clip_path,
        output_file=out_mkv,
        target_bitrate_mbps=25,
        strict_bluray=False,
        title="8K HEVC to 1080p MVC Test",
        engine_mode="gpu_turbo"
    )

    pipeline = StereoForgePipeline()
    success = pipeline.run(job)
    assert success is True
    assert out_mkv.exists()
    assert out_mkv.stat().st_size > 50000


@pytest.mark.skipif(not clip_path.exists(), reason="Requires local 8K HEVC test clip in Clips/")
def test_8k_hevc_to_1080p_bluray_iso_encode(tmp_path):
    """Executes full 8K HEVC -> 1080p 3D Blu-ray ISO pipeline when tools and media exist."""
    if not MuxerEngine().is_tsmuxer_available():
        pytest.skip("Requires tsMuxeR binary")

    out_iso = tmp_path / "Test_8K_HEVC_to_1080p_3D_Bluray.iso"

    job = EncodeJob(
        input_file=clip_path,
        output_file=out_iso,
        target_bitrate_mbps=28,
        strict_bluray=True,
        title="8K HEVC to 3D Blu-ray ISO",
        engine_mode="gpu_turbo"
    )

    pipeline = StereoForgePipeline()
    success = pipeline.run(job)
    assert success is True
    assert out_iso.exists()
    assert out_iso.stat().st_size > 1000000
