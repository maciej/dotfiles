from __future__ import annotations

import os
import re
import subprocess
from enum import Enum
from pathlib import Path

import typer


BYTES_PER_GB = 1000**3


class WhisperModelSize(str, Enum):
    tiny = "tiny"
    base = "base"
    small = "small"
    medium = "medium"
    large = "large"
    turbo = "turbo"


WHISPER_TOTAL_MEMORY_REQUIREMENTS_GB: dict[WhisperModelSize, int] = {
    WhisperModelSize.tiny: 2,
    WhisperModelSize.base: 2,
    WhisperModelSize.small: 4,
    WhisperModelSize.medium: 8,
    WhisperModelSize.turbo: 8,
    WhisperModelSize.large: 16,
}

WHISPER_TOTAL_MEMORY_MINIMUM_BYTES: dict[WhisperModelSize, int] = {
    size: int(required_gb * BYTES_PER_GB * 0.93)
    for size, required_gb in WHISPER_TOTAL_MEMORY_REQUIREMENTS_GB.items()
}


def total_memory_bytes() -> int | None:
    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            page_count = os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError):
            pass
        else:
            if isinstance(page_size, int) and isinstance(page_count, int):
                return page_size * page_count

    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def format_gb(byte_count: int) -> str:
    return f"{byte_count / BYTES_PER_GB:.1f} GB"


def normalize_model_name(model: str) -> str:
    name = Path(model).name.lower()
    name = name.removeprefix("whisper-")
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


def infer_whisper_model_size(model: str) -> WhisperModelSize | None:
    name = normalize_model_name(model)
    parts = set(name.split("-"))

    if "turbo" in parts:
        return WhisperModelSize.turbo
    for size in (
        WhisperModelSize.large,
        WhisperModelSize.medium,
        WhisperModelSize.small,
        WhisperModelSize.base,
        WhisperModelSize.tiny,
    ):
        if size.value in parts:
            return size
    return None


def required_total_memory_bytes(size: WhisperModelSize) -> int:
    return WHISPER_TOTAL_MEMORY_MINIMUM_BYTES[size]


def nominal_required_total_memory_gb(size: WhisperModelSize) -> int:
    return WHISPER_TOTAL_MEMORY_REQUIREMENTS_GB[size]


def require_whisper_model_memory(
    model: str,
    *,
    detected_total_memory_bytes: int | None = None,
) -> None:
    size = infer_whisper_model_size(model)
    if size is None:
        raise typer.BadParameter(
            "Could not infer Whisper model size from "
            f"{model!r}. Use a model name containing tiny, base, small, medium, "
            "large, or turbo so local memory requirements can be checked."
        )

    detected_memory = (
        total_memory_bytes()
        if detected_total_memory_bytes is None
        else detected_total_memory_bytes
    )
    if detected_memory is None:
        raise typer.BadParameter(
            "Could not determine total system memory; refusing to run local "
            f"Whisper model {model!r} without a memory check."
        )

    required_memory = required_total_memory_bytes(size)
    if detected_memory < required_memory:
        nominal_required_memory = nominal_required_total_memory_gb(size)
        raise typer.BadParameter(
            f"Whisper model {model!r} is classified as {size.value} and requires a "
            f"{nominal_required_memory} GB-class system "
            f"({format_gb(required_memory)} OS-visible minimum). This host reports "
            f"{format_gb(detected_memory)}."
        )
