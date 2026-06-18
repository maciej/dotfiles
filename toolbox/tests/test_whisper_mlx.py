from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import mlx_whisper_cli
import whisper_mlx
from mlx_whisper_cli import app

runner = CliRunner()


def test_output_formats_expands_all() -> None:
    assert whisper_mlx.output_formats("all") == ("txt", "vtt", "srt", "tsv", "json")


def test_output_formats_accepts_single_format() -> None:
    assert whisper_mlx.output_formats("srt") == ("srt",)


def test_output_path_for_format_preserves_dotted_stem() -> None:
    assert whisper_mlx.output_path_for_format(
        Path("out"),
        "clip.final",
        "txt",
    ) == Path("out/clip.final.txt")


def test_temperature_schedule_matches_whisper_fallback_default() -> None:
    assert whisper_mlx.temperature_schedule(0, 0.2) == (
        0,
        0.2,
        0.4,
        0.6,
        0.8,
        1.0,
    )


def test_temperature_schedule_can_disable_fallback() -> None:
    assert whisper_mlx.temperature_schedule(0.4, None) == (0.4,)


def test_optional_number_parsers_accept_none() -> None:
    assert whisper_mlx.optional_int("None") is None
    assert whisper_mlx.optional_float("None") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("True", True),
        ("true", True),
        ("1", True),
        ("False", False),
        ("false", False),
        ("0", False),
    ],
)
def test_str_to_bool(value: str, expected: bool) -> None:
    assert whisper_mlx.str_to_bool(value) is expected


def test_str_to_bool_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        whisper_mlx.str_to_bool("maybe")


def test_cli_help_uses_typer_app() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Transcribe audio with mlx-whisper" in result.stdout
    assert "--word-timestamps" in result.stdout
    assert "--quiet" in result.stdout


def test_cli_accepts_hyphenated_typer_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_transcribe_one(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return [Path("out/audio.srt")]

    monkeypatch.setattr(mlx_whisper_cli, "require_binary", lambda name: None)
    monkeypatch.setattr(mlx_whisper_cli, "transcribe_one", fake_transcribe_one)

    result = runner.invoke(
        app,
        [
            "audio.mp3",
            "--output-dir",
            "out",
            "--output-format",
            "srt",
            "--beam-size",
            "4",
            "--word-timestamps",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert captured["args"] == ("audio.mp3",)
    kwargs = captured["kwargs"]
    assert kwargs["output_format"] is whisper_mlx.WhisperOutputFormat.srt
    assert kwargs["verbose"] is False
    assert kwargs["decode_options"]["word_timestamps"] is True
    assert kwargs["decode_options"]["beam_size"] == 4


def test_cli_default_decode_options_match_openai_whisper_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_transcribe_one(*args, **kwargs):
        captured["kwargs"] = kwargs
        return [Path("out/audio.txt")]

    monkeypatch.setattr(mlx_whisper_cli, "require_binary", lambda name: None)
    monkeypatch.setattr(mlx_whisper_cli, "transcribe_one", fake_transcribe_one)

    result = runner.invoke(app, ["audio.mp3", "--quiet"])

    assert result.exit_code == 0
    decode_options = captured["kwargs"]["decode_options"]
    assert decode_options["temperature"] == (0, 0.2, 0.4, 0.6, 0.8, 1.0)
    assert decode_options["best_of"] == 5
    assert decode_options["beam_size"] == 5
    assert decode_options["compression_ratio_threshold"] == 2.4
    assert decode_options["logprob_threshold"] == -1.0
    assert decode_options["no_speech_threshold"] == 0.6
    assert decode_options["hallucination_silence_threshold"] is None
    assert decode_options["condition_on_previous_text"] is True


def test_cli_rejects_subtitle_layout_without_word_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mlx_whisper_cli, "require_binary", lambda name: None)

    result = runner.invoke(
        app,
        [
            "audio.mp3",
            "--max-line-width",
            "42",
        ],
    )

    assert result.exit_code != 0
    assert "requires --word-timestamps" in result.stderr
