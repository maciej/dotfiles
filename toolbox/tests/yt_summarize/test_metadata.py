from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import yt_summarize


def test_format_yyyymmdd_converts_youtube_dates() -> None:
    assert yt_summarize.format_yyyymmdd("20260530") == "2026-05-30"


def test_format_yyyymmdd_preserves_unknown_format() -> None:
    assert yt_summarize.format_yyyymmdd("2026-05-30") == "2026-05-30"


def test_format_count_groups_large_numbers() -> None:
    assert yt_summarize.format_count(357720) == "357,720"


def test_clean_metadata_text_normalizes_and_truncates() -> None:
    text = yt_summarize.clean_metadata_text(
        "One&nbsp;two   three four five",
        max_chars=14,
    )

    assert text == "One two..."


def test_format_list_limits_items() -> None:
    assert yt_summarize.format_list(["a", "b", "c"], limit=2) == "a, b, +1 more"


def test_youtube_video_id_from_url_supports_common_url_shapes() -> None:
    assert (
        yt_summarize.youtube_video_id_from_url(
            "https://www.youtube.com/watch?v=6RplrP49uuk&t=12s"
        )
        == "6RplrP49uuk"
    )
    assert yt_summarize.youtube_video_id_from_url("https://youtu.be/6RplrP49uuk") == "6RplrP49uuk"
    assert (
        yt_summarize.youtube_video_id_from_url("https://www.youtube.com/shorts/6RplrP49uuk")
        == "6RplrP49uuk"
    )


def test_youtube_video_id_from_url_rejects_unknown_urls() -> None:
    assert yt_summarize.youtube_video_id_from_url("https://example.test/watch?v=6RplrP49uuk") is None
    assert yt_summarize.youtube_video_id_from_url("https://www.youtube.com/watch?v=bad") is None


def test_cached_youtube_summary_short_circuits_metadata_load(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "6RplrP49uuk-gpt-5.6-luna-m.md"
    cache_path.write_text("cached summary\n", encoding="utf-8")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("cache hit should not call external dependency path")

    monkeypatch.setattr(yt_summarize, "default_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(yt_summarize, "load_info", fail_if_called)
    monkeypatch.setattr(yt_summarize, "require_binary", fail_if_called)

    result = CliRunner().invoke(
        yt_summarize.app,
        ["https://www.youtube.com/watch?v=6RplrP49uuk"],
    )

    assert result.exit_code == 0, result.output
    assert "cached summary" in result.output


def test_load_info_with_cache_uses_cached_metadata(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "6RplrP49uuk-metadata.json"
    cache_path.write_text(json.dumps({"id": "6RplrP49uuk", "title": "Cached title"}), encoding="utf-8")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("metadata cache hit should not call external dependency path")

    monkeypatch.setattr(yt_summarize, "load_info", fail_if_called)
    monkeypatch.setattr(yt_summarize, "require_binary", fail_if_called)

    info = yt_summarize.load_info_with_cache(
        "https://www.youtube.com/watch?v=6RplrP49uuk",
        tmp_path,
        use_cache=True,
        refresh_cache=False,
    )

    assert info["title"] == "Cached title"


def test_load_info_with_cache_writes_metadata(tmp_path, monkeypatch) -> None:
    required_binaries = []

    def record_required_binary(name: str, message: str | None = None) -> None:
        required_binaries.append(name)

    monkeypatch.setattr(yt_summarize, "require_binary", record_required_binary)
    monkeypatch.setattr(
        yt_summarize,
        "load_info",
        lambda url: {"id": "6RplrP49uuk", "title": "Fresh title"},
    )

    info = yt_summarize.load_info_with_cache(
        "https://www.youtube.com/watch?v=6RplrP49uuk",
        tmp_path,
        use_cache=True,
        refresh_cache=False,
    )

    cached_info = json.loads((tmp_path / "6RplrP49uuk-metadata.json").read_text(encoding="utf-8"))
    assert info["title"] == "Fresh title"
    assert cached_info["title"] == "Fresh title"
    assert required_binaries == ["yt-dlp"]


def test_cached_transcript_and_metadata_avoid_metadata_fetch_for_summary(tmp_path, monkeypatch) -> None:
    (tmp_path / "6RplrP49uuk-metadata.json").write_text(
        json.dumps(
            {
                "id": "6RplrP49uuk",
                "title": "Cached metadata title",
                "webpage_url": "https://www.youtube.com/watch?v=6RplrP49uuk",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "6RplrP49uuk-transcript.en.txt").write_text("cached transcript\n", encoding="utf-8")

    def fail_load_info(url: str) -> dict:
        raise AssertionError("cached metadata should avoid load_info")

    def require_binary_without_ytdlp(name: str, message: str | None = None) -> None:
        if name == "yt-dlp":
            raise AssertionError("cached metadata should avoid yt-dlp")

    def summarize_without_codex(
        text: str,
        model: str,
        size: yt_summarize.SummarySize,
        metadata: str,
        work_dir: Path,
    ) -> str:
        assert text == "cached transcript"
        assert "Title: Cached metadata title" in metadata
        return "new cached-transcript summary"

    monkeypatch.setattr(yt_summarize, "default_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(yt_summarize, "load_info", fail_load_info)
    monkeypatch.setattr(yt_summarize, "require_binary", require_binary_without_ytdlp)
    monkeypatch.setattr(yt_summarize, "summarize", summarize_without_codex)

    result = CliRunner().invoke(
        yt_summarize.app,
        ["https://www.youtube.com/watch?v=6RplrP49uuk"],
    )

    assert result.exit_code == 0, result.output
    assert "new cached-transcript summary" in result.output
    assert (tmp_path / "6RplrP49uuk-gpt-5.6-luna-m.md").read_text(encoding="utf-8").strip() == (
        "new cached-transcript summary"
    )


def test_format_chapters_renders_timestamps() -> None:
    chapters = [
        {"start_time": 0, "title": "Intro"},
        {"start_time": 75.2, "title": "Main point"},
    ]

    assert yt_summarize.format_chapters(chapters) == "- 0:00 Intro\n- 1:15 Main point"


def test_source_metadata_includes_compact_video_context() -> None:
    metadata = yt_summarize.source_metadata(
        {
            "title": "They're Hiding The World's Rarest Cars In Poland",
            "webpage_url": "https://www.youtube.com/watch?v=7PFI-2zbP04",
            "channel": "Daily Driven Exotics Clips",
            "upload_date": "20260530",
            "duration_string": "11:39",
            "language": "en",
            "categories": ["People & Blogs"],
            "tags": ["Bugatti", "Pagani"],
            "view_count": 357720,
            "like_count": 6203,
            "comment_count": 269,
            "description": "Hidden in Katowice, Poland, there is a hypercar dealership.",
            "chapters": [{"start_time": 0, "title": "Intro"}],
        },
        "https://youtu.be/7PFI-2zbP04",
        "en auto captions",
    )

    assert "Title: They're Hiding The World's Rarest Cars In Poland" in metadata
    assert "Channel: Daily Driven Exotics Clips" in metadata
    assert "Upload date: 2026-05-30" in metadata
    assert "Duration: 11:39" in metadata
    assert "Language: en" in metadata
    assert "Categories: People & Blogs" in metadata
    assert "Tags: Bugatti, Pagani" in metadata
    assert "Engagement: views: 357,720; likes: 6,203; comments: 269" in metadata
    assert "Transcript source: en auto captions" in metadata
    assert "Uploader description:" in metadata
    assert "Chapters:\n- 0:00 Intro" in metadata


def test_source_metadata_omits_missing_optional_values() -> None:
    metadata = yt_summarize.source_metadata({}, "https://example.test/video", None)

    assert metadata == "Title: https://example.test/video\nURL: https://example.test/video"
