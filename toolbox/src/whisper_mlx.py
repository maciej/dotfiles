from __future__ import annotations

import contextlib
import importlib
import io
import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from rich.progress import Progress, TaskID
from whisper_memory import require_whisper_model_memory

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")


DEFAULT_TRANSCRIBE_MODEL = "mlx-community/whisper-large-v3-turbo"
DEFAULT_TRANSLATE_MODEL = "mlx-community/whisper-medium-mlx"
OUTPUT_FORMATS = ("txt", "vtt", "srt", "tsv", "json")
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TEMPERATURE_INCREMENT_ON_FALLBACK = 0.2
DEFAULT_BEST_OF = 5
DEFAULT_BEAM_SIZE = 5
DEFAULT_PATIENCE = None
DEFAULT_LENGTH_PENALTY = None
DEFAULT_SUPPRESS_TOKENS = "-1"
DEFAULT_CONDITION_ON_PREVIOUS_TEXT = True
DEFAULT_FP16 = True
DEFAULT_COMPRESSION_RATIO_THRESHOLD = 2.4
DEFAULT_LOGPROB_THRESHOLD = -1.0
DEFAULT_NO_SPEECH_THRESHOLD = 0.6
DEFAULT_WORD_TIMESTAMPS = False
DEFAULT_PREPEND_PUNCTUATIONS = "\"'“¿([{-"
DEFAULT_APPEND_PUNCTUATIONS = "\"'.。,，!！?？:：”)]}、"
DEFAULT_CLIP_TIMESTAMPS = "0"
DEFAULT_HALLUCINATION_SILENCE_THRESHOLD = None
DEFAULT_RETURN_CANDIDATES = False


class WhisperTask(str, Enum):
    transcribe = "transcribe"
    translate = "translate"


class WhisperOutputFormat(str, Enum):
    txt = "txt"
    vtt = "vtt"
    srt = "srt"
    tsv = "tsv"
    json = "json"
    all = "all"


class RichTqdm:
    def __init__(
        self,
        progress: Progress,
        description: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.progress = progress
        self.description = description
        self.total = kwargs.get("total")
        self.disable = kwargs.get("disable", False)
        self.task_id: Optional[TaskID] = None

        if not self.disable:
            self.task_id = self.progress.add_task(
                self.description,
                total=self.total,
            )

    def __enter__(self) -> RichTqdm:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.close()
        return False

    def update(self, n: float = 1) -> None:
        if self.task_id is not None:
            self.progress.update(self.task_id, advance=n)

    def close(self) -> None:
        if self.task_id is not None and self.total is not None:
            self.progress.update(self.task_id, completed=self.total)


def rich_tqdm_factory(progress: Progress, description: str):
    def rich_tqdm(*args: Any, **kwargs: Any) -> RichTqdm:
        return RichTqdm(progress, description, *args, **kwargs)

    return rich_tqdm


def optional_int(value: str) -> int | None:
    return None if value == "None" else int(value)


def optional_float(value: str) -> float | None:
    return None if value == "None" else float(value)


def str_to_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"expected one of True or False, got {value!r}")


def temperature_schedule(
    temperature: float,
    increment_on_fallback: float | None,
) -> tuple[float, ...]:
    if increment_on_fallback is None:
        return (temperature,)
    if increment_on_fallback <= 0:
        raise ValueError("--temperature_increment_on_fallback must be positive or None")

    values: list[float] = []
    current = temperature
    while current <= 1.0 + 1e-6:
        values.append(round(current, 10))
        current += increment_on_fallback
    return tuple(values) or (temperature,)


def output_formats(output_format: str | WhisperOutputFormat) -> tuple[str, ...]:
    value = output_format.value if isinstance(output_format, WhisperOutputFormat) else output_format
    if value == "all":
        return OUTPUT_FORMATS
    if value not in OUTPUT_FORMATS:
        raise ValueError(f"unsupported output format: {value}")
    return (value,)


def output_path_for_format(output_dir: Path, output_name: str, output_format: str) -> Path:
    return output_dir / f"{Path(output_name).name}.{output_format}"


def transcribe_audio(
    audio: str | Path | Any,
    *,
    model: str,
    progress: Progress | None = None,
    progress_description: str = "Running mlx-whisper locally...",
    suppress_stdout: bool = True,
    check_memory: bool = True,
    **decode_options: Any,
) -> dict[str, Any]:
    if check_memory:
        require_whisper_model_memory(model)

    transcribe_module = importlib.import_module("mlx_whisper.transcribe")
    original_tqdm = transcribe_module.tqdm.tqdm
    if progress is not None:
        transcribe_module.tqdm.tqdm = rich_tqdm_factory(progress, progress_description)

    stdout_context = (
        contextlib.redirect_stdout(io.StringIO())
        if suppress_stdout
        else contextlib.nullcontext()
    )
    audio_input = str(audio) if isinstance(audio, Path) else audio

    try:
        with stdout_context:
            result = transcribe_module.transcribe(
                audio_input,
                path_or_hf_repo=model,
                **decode_options,
            )
    finally:
        transcribe_module.tqdm.tqdm = original_tqdm

    return result


def write_result_file(
    result: dict[str, Any],
    output_path: Path,
    *,
    output_format: str,
    writer_options: dict[str, Any] | None = None,
) -> Path:
    writers_module = importlib.import_module("mlx_whisper.writers")
    writer_classes = {
        "txt": writers_module.WriteTXT,
        "vtt": writers_module.WriteVTT,
        "srt": writers_module.WriteSRT,
        "tsv": writers_module.WriteTSV,
        "json": writers_module.WriteJSON,
    }
    try:
        writer_class = writer_classes[output_format]
    except KeyError as exc:
        raise ValueError(f"unsupported output format: {output_format}") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = writer_class(str(output_path.parent))
    with output_path.open("wt", encoding="utf-8") as output_file:
        writer.write_result(result, file=output_file, **(writer_options or {}))
    return output_path


def write_result_files(
    result: dict[str, Any],
    *,
    output_dir: Path,
    output_name: str,
    output_format: str | WhisperOutputFormat,
    writer_options: dict[str, Any] | None = None,
) -> list[Path]:
    return [
        write_result_file(
            result,
            output_path_for_format(output_dir, output_name, current_format),
            output_format=current_format,
            writer_options=writer_options,
        )
        for current_format in output_formats(output_format)
    ]
