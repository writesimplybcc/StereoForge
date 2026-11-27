"""Unit tests for Multi-Track Audio Preservation & Batch Queue System."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from stereoforge.pipeline.ingest import MediaProfile, StereoFormat
from stereoforge.pipeline.orchestrator import EncodeJob, JobResult, BatchProgress, StereoForgePipeline
from stereoforge.cli import scan_batch_jobs
from stereoforge.pipeline.muxer import MuxerEngine


def test_batch_progress_and_job_result():
    job1 = EncodeJob(input_file=Path("movie1.mp4"), output_file=Path("movie1_3D.mkv"))
    job2 = EncodeJob(input_file=Path("movie2.mp4"), output_file=Path("movie2_3D.mkv"))

    res1 = JobResult(job=job1, success=True, elapsed_seconds=12.5, output_size_bytes=1024000)
    assert res1.success is True
    assert res1.elapsed_seconds == 12.5
    assert res1.error is None

    res2 = JobResult(job=job2, success=False, error="Simulated codec error", elapsed_seconds=1.2)
    assert res2.success is False
    assert "Simulated codec error" in res2.error

    batch = BatchProgress(
        current_job_index=1,
        total_jobs=2,
        current_job=job2,
        completed_jobs=1,
        failed_jobs=0,
        overall_progress=0.75,
        job_results=[res1]
    )
    assert batch.current_job_index == 1
    assert batch.total_jobs == 2
    assert batch.completed_jobs == 1
    assert batch.overall_progress == 0.75


def test_scan_batch_jobs_dual_files_and_singles():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        out_dir = tmp_path / "Output"
        out_dir.mkdir()

        # Create mock video files
        (tmp_path / "Avatar_left.mp4").write_text("dummy")
        (tmp_path / "Avatar_right.mp4").write_text("dummy")
        (tmp_path / "Hugo_SBS.mkv").write_text("dummy")
        (tmp_path / "AlreadyEncoded_3D.mkv").write_text("dummy")  # Should be skipped

        jobs = scan_batch_jobs(
            batch_dir=tmp_path,
            output_dir=out_dir,
            output_format="mkv",
            bitrate=30,
            engine_mode="native_mvc"
        )

        assert len(jobs) == 2  # Avatar pair (1 job) + Hugo_SBS (1 job)

        # Check Avatar pair
        avatar_job = next(j for j in jobs if "Avatar" in j.input_file.name)
        assert avatar_job.right_file is not None
        assert "right" in avatar_job.right_file.name.lower()
        assert avatar_job.layout_override == StereoFormat.DUAL_FILES

        # Check Hugo single file
        hugo_job = next(j for j in jobs if "Hugo" in j.input_file.name)
        assert hugo_job.right_file is None
        assert hugo_job.output_file.name == "Hugo_SBS_3D.mkv"


def test_pipeline_run_batch_execution():
    pipeline = StereoForgePipeline()

    job1 = EncodeJob(input_file=Path("mock1.mp4"), output_file=Path("mock1_3D.mkv"))
    job2 = EncodeJob(input_file=Path("mock2.mp4"), output_file=Path("mock2_3D.mkv"))

    progress_events = []
    def on_batch_prog(bp: BatchProgress):
        progress_events.append(bp.overall_progress)

    # Mock pipeline.run to succeed on job1 and fail on job2
    def mock_run(job, progress_cb=None):
        if "mock1" in job.input_file.name:
            if progress_cb:
                progress_cb("Pass 1", 0.5)
                progress_cb("Pass 2", 1.0)
            return True
        else:
            raise RuntimeError("Corrupted audio track")

    with patch.object(pipeline, "run", side_effect=mock_run):
        results = pipeline.run_batch(
            jobs=[job1, job2],
            batch_progress_cb=on_batch_prog,
            stop_on_error=False
        )

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False
    assert "Corrupted audio track" in results[1].error
    assert len(progress_events) > 0
    assert progress_events[-1] == 1.0


def test_tsmuxer_multi_track_meta_generation():
    muxer = MuxerEngine()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        base_video = tmp_path / "base.264"
        dep_mvc = tmp_path / "dep.mvc"
        out_iso = tmp_path / "output.iso"
        base_video.write_bytes(b"\x00\x00\x00\x01\x67")
        dep_mvc.write_bytes(b"\x00\x00\x00\x01\x20")

        audio_streams = [
            {"audio_index": 0, "codec": "truehd", "language": "eng"},
            {"audio_index": 1, "codec": "dts", "language": "spa"},
            {"audio_index": 2, "codec": "opus", "language": "fre"}
        ]

        # Intercept subprocess.run to verify the generated .meta file
        saved_meta_content = []
        def mock_subprocess_run(cmd, *args, **kwargs):
            if any(str(a).endswith(".meta") for a in cmd):
                meta_p = next(Path(a) for a in cmd if str(a).endswith(".meta"))
                saved_meta_content.append(meta_p.read_text(encoding="utf-8"))
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            with patch.object(muxer, "is_tsmuxer_available", return_value=True):
                success = muxer.mux_3d_bluray(
                    base_video_path=base_video,
                    dependent_mvc_path=dep_mvc,
                    output_dir_or_iso=out_iso,
                    audio_source_path=base_video,
                    audio_streams=audio_streams,
                    fps="23.976"
                )

        assert success is True
        assert len(saved_meta_content) == 1
        meta = saved_meta_content[0]

        # Verify TrueHD, DTS, and transcoded AC3 meta directives
        assert "V_MPEG4/ISO/AVC" in meta
        assert "V_MPEG4/ISO/MVC" in meta
        assert "A_TRUE-HD" in meta
        assert "lang=eng" in meta
        assert "A_DTS" in meta
        assert "lang=spa" in meta
        assert "A_AC3" in meta  # Opus transcoded to standard 640k AC-3
        assert "lang=fre" in meta
