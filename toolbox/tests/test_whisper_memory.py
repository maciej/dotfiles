from __future__ import annotations

import pytest
import typer

import whisper_memory
from whisper_memory import BYTES_PER_GB, WhisperModelSize


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("mlx-community/whisper-large-v3-turbo", WhisperModelSize.turbo),
        ("mlx-community/whisper-medium-mlx", WhisperModelSize.medium),
        ("openai/whisper-small.en", WhisperModelSize.small),
        ("whisper-base", WhisperModelSize.base),
        ("tiny.en", WhisperModelSize.tiny),
        ("/models/faster-whisper-large-v3", WhisperModelSize.large),
    ],
)
def test_infer_whisper_model_size(model: str, expected: WhisperModelSize) -> None:
    assert whisper_memory.infer_whisper_model_size(model) == expected


def test_require_whisper_model_memory_accepts_sufficient_total_memory() -> None:
    whisper_memory.require_whisper_model_memory(
        "mlx-community/whisper-large-v3-turbo",
        detected_total_memory_bytes=8 * BYTES_PER_GB,
    )


def test_require_whisper_model_memory_accepts_reserved_raspberry_pi_memory() -> None:
    whisper_memory.require_whisper_model_memory(
        "mlx-community/whisper-medium-mlx",
        detected_total_memory_bytes=int(7.5 * BYTES_PER_GB),
    )


def test_require_whisper_model_memory_rejects_insufficient_total_memory() -> None:
    with pytest.raises(typer.BadParameter, match="requires a 16 GB-class system"):
        whisper_memory.require_whisper_model_memory(
            "mlx-community/whisper-large-v3",
            detected_total_memory_bytes=8 * BYTES_PER_GB,
        )


def test_require_whisper_model_memory_rejects_unknown_model_size() -> None:
    with pytest.raises(typer.BadParameter, match="Could not infer Whisper model size"):
        whisper_memory.require_whisper_model_memory(
            "example/speech-model",
            detected_total_memory_bytes=16 * BYTES_PER_GB,
        )
