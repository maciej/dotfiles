from __future__ import annotations

import contextlib
import importlib
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import typer
from system_dependencies import require_binary
from whisper_memory import require_whisper_model_memory
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")


DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"

app = typer.Typer(
    add_completion=False,
    help="Generate local SRT subtitles from a video file with mlx-whisper.",
)
console = Console(stderr=True)


def require_ffmpeg() -> None:
    require_binary("ffmpeg")


def get_media_duration(path: Path) -> Optional[float]:
    if shutil.which("ffprobe") is None:
        return None

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        duration = float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None

    return duration if duration > 0 else None


def default_output_path(video: Path) -> Path:
    return video.with_suffix(".srt")


def parse_ffmpeg_progress_seconds(line: str) -> Optional[float]:
    key, separator, value = line.strip().partition("=")
    if not separator:
        return None
    if key in {"out_time_us", "out_time_ms"}:
        try:
            return int(value) / 1_000_000
        except ValueError:
            return None
    return None


def extract_audio(
    video: Path,
    audio: Path,
    *,
    progress: Progress,
    task_id: TaskID,
    duration: Optional[float],
    overwrite: bool,
) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-progress",
        "pipe:1",
        "-y" if overwrite else "-n",
        "-i",
        str(video),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(audio),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    for line in process.stdout:
        seconds = parse_ffmpeg_progress_seconds(line)
        if seconds is not None and duration is not None:
            progress.update(task_id, completed=min(seconds, duration))

    stderr = process.stderr.read()
    return_code = process.wait()
    if return_code:
        if stderr.strip():
            console.print(stderr.strip())
        raise subprocess.CalledProcessError(return_code, command, stderr=stderr)

    if duration is not None:
        progress.update(task_id, completed=duration)


class RichTqdm:
    def __init__(self, progress: Progress, *args, **kwargs):
        self.progress = progress
        self.total = kwargs.get("total")
        self.disable = kwargs.get("disable", False)
        self.task_id: Optional[TaskID] = None

        if not self.disable:
            self.task_id = self.progress.add_task(
                "Transcribing locally with mlx-whisper...",
                total=self.total,
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    def update(self, n: float = 1) -> None:
        if self.task_id is not None:
            self.progress.update(self.task_id, advance=n)

    def close(self) -> None:
        if self.task_id is not None and self.total is not None:
            self.progress.update(self.task_id, completed=self.total)


def rich_tqdm_factory(progress: Progress):
    def rich_tqdm(*args, **kwargs):
        return RichTqdm(progress, *args, **kwargs)

    return rich_tqdm


@app.command()
def main(
    video: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Video file to transcribe.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="SRT output path. Defaults to VIDEO_BASENAME.srt next to the input.",
    ),
    model: str = typer.Option(
        DEFAULT_MODEL,
        "--whisper-model",
        help="MLX Whisper model directory or Hugging Face repo.",
    ),
    language: Optional[str] = typer.Option(
        None,
        "--whisper-language",
        help="Spoken language code, such as en or pl. Omit to auto-detect.",
    ),
    beam_size: Optional[int] = typer.Option(
        None,
        "--whisper-beam-size",
        min=1,
        help="Beam size for temperature-0 decoding.",
    ),
    patience: Optional[float] = typer.Option(
        None,
        "--whisper-patience",
        min=0.0,
        help="Optional patience value for beam decoding.",
    ),
    word_timestamps: bool = typer.Option(
        True,
        "--whisper-word-timestamps/--no-whisper-word-timestamps",
        help="Use word-level timestamps before SRT line wrapping.",
    ),
    hallucination_silence_threshold: Optional[float] = typer.Option(
        2.0,
        "--whisper-hallucination-silence-threshold",
        min=0.0,
        help="Skip silent periods longer than this many seconds when a possible hallucination is detected.",
    ),
    max_line_width: Optional[int] = typer.Option(
        None,
        "--max-line-width",
        min=1,
        help="Maximum subtitle line width. Requires --whisper-word-timestamps.",
    ),
    max_line_count: Optional[int] = typer.Option(
        None,
        "--max-line-count",
        min=1,
        help="Maximum subtitle line count. Requires --whisper-word-timestamps and --max-line-width.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite an existing SRT output file.",
    ),
) -> None:
    require_ffmpeg()

    output_path = output or default_output_path(video)
    output_path = output_path.with_suffix(".srt")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not overwrite:
        raise typer.BadParameter(
            f"{output_path} already exists. Pass --overwrite to replace it."
        )

    if (max_line_width or max_line_count) and not word_timestamps:
        raise typer.BadParameter(
            "--max-line-width and --max-line-count require --whisper-word-timestamps."
        )
    if max_line_count and not max_line_width:
        raise typer.BadParameter("--max-line-count requires --max-line-width.")

    require_whisper_model_memory(model)

    console.print(
        Panel.fit(
            f"[bold]{video.name}[/bold]\nmodel: [cyan]{model}[/cyan]\noutput: {output_path}",
            title="mlx-subtitles",
        )
    )

    duration = get_media_duration(video)

    with tempfile.TemporaryDirectory(prefix="mlx-subtitles-") as temp_dir:
        audio_path = Path(temp_dir) / f"{video.stem}.wav"

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=False,
            ) as progress:
                extract_task = progress.add_task(
                    "Extracting audio with ffmpeg...",
                    total=duration,
                )
                extract_audio(
                    video,
                    audio_path,
                    progress=progress,
                    task_id=extract_task,
                    duration=duration,
                    overwrite=True,
                )
                if duration is None:
                    progress.update(extract_task, description="Audio extracted")
                else:
                    progress.update(
                        extract_task,
                        description="Audio extracted",
                        completed=duration,
                    )

                transcribe_module = importlib.import_module("mlx_whisper.transcribe")
                writers_module = importlib.import_module("mlx_whisper.writers")
                original_tqdm = transcribe_module.tqdm.tqdm
                transcribe_module.tqdm.tqdm = rich_tqdm_factory(progress)

                decode_options = {
                    "language": language,
                    "word_timestamps": word_timestamps,
                    "hallucination_silence_threshold": hallucination_silence_threshold,
                    "verbose": False,
                }
                if beam_size is not None:
                    decode_options["beam_size"] = beam_size
                if patience is not None:
                    decode_options["patience"] = patience

                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = transcribe_module.transcribe(
                            str(audio_path),
                            path_or_hf_repo=model,
                            **decode_options,
                        )
                finally:
                    transcribe_module.tqdm.tqdm = original_tqdm

                write_task = progress.add_task("Writing SRT subtitles...", total=1)
                writer_output_dir = output_path.parent
                writer_output_name = output_path.stem
                if "." in writer_output_name:
                    writer_output_dir = Path(temp_dir)
                    writer_output_name = "subtitles"

                writer = writers_module.WriteSRT(str(writer_output_dir))
                writer(
                    result,
                    writer_output_name,
                    max_line_width=max_line_width,
                    max_line_count=max_line_count,
                )
                generated_output = (writer_output_dir / writer_output_name).with_suffix(
                    ".srt"
                )
                if generated_output != output_path:
                    shutil.move(generated_output, output_path)
                progress.update(
                    write_task,
                    description="SRT subtitles written",
                    completed=1,
                )
        except subprocess.CalledProcessError as exc:
            raise typer.Exit(exc.returncode) from exc

    console.print(f"[green]Wrote[/green] {output_path}")
