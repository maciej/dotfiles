from __future__ import annotations

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
