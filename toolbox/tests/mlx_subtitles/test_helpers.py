from __future__ import annotations

from pathlib import Path

import mlx_subtitles


def test_default_output_path_uses_srt_suffix() -> None:
    assert mlx_subtitles.default_output_path(Path("video.mov")) == Path("video.srt")


def test_default_output_path_replaces_existing_suffix() -> None:
    assert mlx_subtitles.default_output_path(Path("clip.final.mp4")) == Path(
        "clip.final.srt"
    )


def test_parse_ffmpeg_progress_seconds_reads_microsecond_fields() -> None:
    assert mlx_subtitles.parse_ffmpeg_progress_seconds("out_time_us=2500000") == 2.5
    assert mlx_subtitles.parse_ffmpeg_progress_seconds("out_time_ms=3000000") == 3.0


def test_parse_ffmpeg_progress_seconds_ignores_other_fields() -> None:
    assert mlx_subtitles.parse_ffmpeg_progress_seconds("progress=continue") is None
    assert mlx_subtitles.parse_ffmpeg_progress_seconds("out_time_us=not-a-number") is None
    assert mlx_subtitles.parse_ffmpeg_progress_seconds("malformed") is None
