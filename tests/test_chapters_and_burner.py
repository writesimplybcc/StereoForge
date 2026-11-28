"""Unit tests for chapter markers, disc media sizing advisor, and burner engine."""

import tempfile
from pathlib import Path
from stereoforge.pipeline.chapters import (
    Chapter,
    format_tsmuxer_chapter_option,
    generate_interval_chapters,
    create_ogm_chapters_file
)
from stereoforge.pipeline.burner import (
    DiscMediaAdvisor,
    BurnerEngine,
    detect_optical_drives,
    BD25_MAX_BYTES,
    BD50_MAX_BYTES
)


def test_chapter_timestamps():
    c1 = Chapter(index=1, start_seconds=0.0, title="Intro")
    assert c1.timestamp_hms_ms == "00:00:00.000"

    c2 = Chapter(index=2, start_seconds=305.5, title="Flight")
    # 305.5s = 5m 5.5s = 00:05:05.500
    assert c2.timestamp_hms_ms == "00:05:05.500"

    c3 = Chapter(index=3, start_seconds=3661.123, title="Ending")
    # 3661.123s = 1h 1m 1.123s = 01:01:01.123
    assert c3.timestamp_hms_ms == "01:01:01.123"


def test_tsmuxer_chapter_options():
    # Empty or single chapter defaults to auto-chapters
    assert format_tsmuxer_chapter_option([], auto_interval_minutes=5) == "--auto-chapters=5"
    assert format_tsmuxer_chapter_option([Chapter(1, 0.0)], auto_interval_minutes=10) == "--auto-chapters=10"

    # Multi-chapter outputs custom semicolon-separated timestamps
    chaps = [
        Chapter(1, 0.0),
        Chapter(2, 300.0),
        Chapter(3, 600.0)
    ]
    opt = format_tsmuxer_chapter_option(chaps)
    assert opt == "--custom-chapters=00:00:00.000;00:05:00.000;00:10:00.000"


def test_ogm_chapters_file_generation():
    chaps = [
        Chapter(1, 0.0, "Scene 1"),
        Chapter(2, 125.250, "Scene 2")
    ]
    with tempfile.TemporaryDirectory() as td:
        out_f = Path(td) / "test_chap.txt"
        create_ogm_chapters_file(chaps, out_f)
        assert out_f.exists()
        content = out_f.read_text(encoding="utf-8")
        assert "CHAPTER01=00:00:00.000" in content
        assert "CHAPTER01NAME=Scene 1" in content
        assert "CHAPTER02=00:02:05.250" in content
        assert "CHAPTER02NAME=Scene 2" in content


def test_disc_media_advisor_bd25():
    # 18 GB ISO -> fits on BD-25
    size = int(18 * 1024 * 1024 * 1024)
    res = DiscMediaAdvisor.analyze(size)
    assert res["fits_bd25"] is True
    assert res["fits_bd50"] is True
    assert "BD-25" in res["recommended_media"]


def test_disc_media_advisor_bd50():
    # 35 GB ISO -> exceeds BD-25, requires BD-50
    size = int(35 * 1024 * 1024 * 1024)
    res = DiscMediaAdvisor.analyze(size)
    assert res["fits_bd25"] is False
    assert res["fits_bd50"] is True
    assert "BD-50" in res["recommended_media"]


def test_disc_media_advisor_bd100():
    # 70 GB ISO -> exceeds BD-50, requires BDXL
    size = int(70 * 1024 * 1024 * 1024)
    res = DiscMediaAdvisor.analyze(size)
    assert res["fits_bd25"] is False
    assert res["fits_bd50"] is False
    assert res["fits_bd100"] is True
    assert "BD-100" in res["recommended_media"]


def test_burner_engine_detection():
    engine = BurnerEngine()
    pref = engine.get_preferred_burner()
    assert "engine" in pref
    assert "label" in pref


def test_detect_optical_drives_call():
    # Should not crash on any system
    drives = detect_optical_drives()
    assert isinstance(drives, list)
