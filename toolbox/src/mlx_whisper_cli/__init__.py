from __future__ import annotations

import contextlib
import importlib
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from system_dependencies import require_binary
from whisper_mlx import (
    DEFAULT_APPEND_PUNCTUATIONS,
    DEFAULT_BEAM_SIZE,
    DEFAULT_BEST_OF,
    DEFAULT_CLIP_TIMESTAMPS,
    DEFAULT_COMPRESSION_RATIO_THRESHOLD,
    DEFAULT_CONDITION_ON_PREVIOUS_TEXT,
    DEFAULT_FP16,
    DEFAULT_HALLUCINATION_SILENCE_THRESHOLD,
    DEFAULT_LENGTH_PENALTY,
    DEFAULT_LOGPROB_THRESHOLD,
    DEFAULT_NO_SPEECH_THRESHOLD,
    DEFAULT_PATIENCE,
    DEFAULT_PREPEND_PUNCTUATIONS,
    DEFAULT_RETURN_CANDIDATES,
    DEFAULT_SUPPRESS_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPERATURE_INCREMENT_ON_FALLBACK,
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_WORD_TIMESTAMPS,
    WhisperOutputFormat,
    WhisperTask,
    output_formats,
    temperature_schedule,
    transcribe_audio,
    write_result_files,
)

console = Console(stderr=True)
app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Transcribe audio with mlx-whisper.",
)


def load_audio_from_stdin() -> Any:
    audio_module = importlib.import_module("mlx_whisper.audio")
    return audio_module.load_audio(from_stdin=True)


def validate_writer_options(
    *,
    word_timestamps: bool,
    highlight_words: bool,
    max_line_width: int | None,
    max_line_count: int | None,
    max_words_per_line: int | None,
) -> dict[str, Any]:
    writer_options = {
        "highlight_words": highlight_words,
        "max_line_count": max_line_count,
        "max_line_width": max_line_width,
        "max_words_per_line": max_words_per_line,
    }

    if not word_timestamps:
        for option, value in writer_options.items():
            if value:
                raise typer.BadParameter(
                    f"--{option.replace('_', '-')} requires --word-timestamps"
                )
    if max_line_count and not max_line_width:
        console.print(
            "[yellow]Warning:[/yellow] --max-line-count has no effect without "
            "--max-line-width"
        )
    if max_words_per_line and max_line_width:
        console.print(
            "[yellow]Warning:[/yellow] --max-words-per-line has no effect with "
            "--max-line-width"
        )

    return writer_options


def transcribe_one(
    audio_arg: str,
    *,
    model: str,
    output_dir: Path,
    output_name: str | None,
    output_format: WhisperOutputFormat,
    verbose: bool,
    decode_options: dict[str, Any],
    writer_options: dict[str, Any],
) -> list[Path]:
    if audio_arg == "-":
        audio_input = load_audio_from_stdin()
        current_output_name = output_name or "content"
    else:
        audio_input = audio_arg
        current_output_name = output_name or Path(audio_arg).stem

    progress_context = (
        Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        )
        if not verbose
        else contextlib.nullcontext(None)
    )

    with progress_context as progress:
        result = transcribe_audio(
            audio_input,
            model=model,
            progress=progress,
            suppress_stdout=not verbose,
            **decode_options,
        )

    return write_result_files(
        result,
        output_dir=output_dir,
        output_name=current_output_name,
        output_format=output_format,
        writer_options=writer_options,
    )


@app.command(help="Transcribe audio with mlx-whisper.")
def main(
    audio: Annotated[
        list[str],
        typer.Argument(help="Audio file(s) to transcribe. Use '-' to read from stdin."),
    ],
    model: Annotated[
        str,
        typer.Option("--model", help="MLX Whisper model directory or Hugging Face repo."),
    ] = DEFAULT_TRANSCRIBE_MODEL,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "--output_dir",
            "-o",
            file_okay=False,
            dir_okay=True,
            writable=True,
            resolve_path=True,
            help="Directory to save output files.",
        ),
    ] = Path("."),
    output_format: Annotated[
        WhisperOutputFormat,
        typer.Option(
            "--output-format",
            "--output_format",
            "-f",
            help="Output format to write.",
        ),
    ] = WhisperOutputFormat.all,
    output_name: Annotated[
        Optional[str],
        typer.Option(
            "--output-name",
            "--output_name",
            help="Output file basename before the format extension.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose/--quiet",
            help="Print decoded segments instead of showing a Rich progress bar.",
        ),
    ] = True,
    task: Annotated[
        WhisperTask,
        typer.Option("--task", help="Speech recognition or speech translation."),
    ] = WhisperTask.transcribe,
    language: Annotated[
        Optional[str],
        typer.Option(
            "--language",
            help="Language spoken in the audio. Omit to auto-detect.",
        ),
    ] = None,
    temperature: Annotated[
        float,
        typer.Option("--temperature", help="Temperature to use for sampling."),
    ] = DEFAULT_TEMPERATURE,
    best_of: Annotated[
        Optional[int],
        typer.Option(
            "--best-of",
            "--best_of",
            min=1,
            help="Number of candidates when sampling with non-zero temperature.",
        ),
    ] = DEFAULT_BEST_OF,
    beam_size: Annotated[
        Optional[int],
        typer.Option(
            "--beam-size",
            "--beam_size",
            min=1,
            help="Number of beams in beam search when temperature is zero.",
        ),
    ] = DEFAULT_BEAM_SIZE,
    patience: Annotated[
        Optional[float],
        typer.Option("--patience", min=0.0, help="Optional beam decoding patience."),
    ] = DEFAULT_PATIENCE,
    length_penalty: Annotated[
        Optional[float],
        typer.Option(
            "--length-penalty",
            "--length_penalty",
            help="Optional token length penalty coefficient.",
        ),
    ] = DEFAULT_LENGTH_PENALTY,
    suppress_tokens: Annotated[
        str,
        typer.Option(
            "--suppress-tokens",
            "--suppress_tokens",
            help="Comma-separated token ids to suppress during sampling.",
        ),
    ] = DEFAULT_SUPPRESS_TOKENS,
    initial_prompt: Annotated[
        Optional[str],
        typer.Option(
            "--initial-prompt",
            "--initial_prompt",
            help="Optional text prompt for the first window.",
        ),
    ] = None,
    condition_on_previous_text: Annotated[
        bool,
        typer.Option(
            "--condition-on-previous-text/--no-condition-on-previous-text",
            help="Provide previous output as a prompt for the next window.",
        ),
    ] = DEFAULT_CONDITION_ON_PREVIOUS_TEXT,
    fp16: Annotated[
        bool,
        typer.Option("--fp16/--fp32", help="Use fp16 inference."),
    ] = DEFAULT_FP16,
    temperature_increment_on_fallback: Annotated[
        float,
        typer.Option(
            "--temperature-increment-on-fallback",
            "--temperature_increment_on_fallback",
            min=0.0,
            help="Temperature increment for fallback decoding. Use 0 to disable.",
        ),
    ] = DEFAULT_TEMPERATURE_INCREMENT_ON_FALLBACK,
    compression_ratio_threshold: Annotated[
        Optional[float],
        typer.Option(
            "--compression-ratio-threshold",
            "--compression_ratio_threshold",
            help="Fail decoding above this gzip compression ratio.",
        ),
    ] = DEFAULT_COMPRESSION_RATIO_THRESHOLD,
    logprob_threshold: Annotated[
        Optional[float],
        typer.Option(
            "--logprob-threshold",
            "--logprob_threshold",
            help="Fail decoding below this average log probability.",
        ),
    ] = DEFAULT_LOGPROB_THRESHOLD,
    no_speech_threshold: Annotated[
        Optional[float],
        typer.Option(
            "--no-speech-threshold",
            "--no_speech_threshold",
            help="Treat segments above this no-speech probability as silence.",
        ),
    ] = DEFAULT_NO_SPEECH_THRESHOLD,
    word_timestamps: Annotated[
        bool,
        typer.Option(
            "--word-timestamps/--no-word-timestamps",
            help="Extract word-level timestamps.",
        ),
    ] = DEFAULT_WORD_TIMESTAMPS,
    prepend_punctuations: Annotated[
        str,
        typer.Option(
            "--prepend-punctuations",
            "--prepend_punctuations",
            help="Punctuation symbols to merge with the next word.",
        ),
    ] = DEFAULT_PREPEND_PUNCTUATIONS,
    append_punctuations: Annotated[
        str,
        typer.Option(
            "--append-punctuations",
            "--append_punctuations",
            help="Punctuation symbols to merge with the previous word.",
        ),
    ] = DEFAULT_APPEND_PUNCTUATIONS,
    highlight_words: Annotated[
        bool,
        typer.Option(
            "--highlight-words/--no-highlight-words",
            help="Underline each word as it is spoken in SRT and VTT outputs.",
        ),
    ] = False,
    max_line_width: Annotated[
        Optional[int],
        typer.Option(
            "--max-line-width",
            "--max_line_width",
            min=1,
            help="Maximum number of characters in a subtitle line.",
        ),
    ] = None,
    max_line_count: Annotated[
        Optional[int],
        typer.Option(
            "--max-line-count",
            "--max_line_count",
            min=1,
            help="Maximum number of lines in a subtitle segment.",
        ),
    ] = None,
    max_words_per_line: Annotated[
        Optional[int],
        typer.Option(
            "--max-words-per-line",
            "--max_words_per_line",
            min=1,
            help="Maximum number of words in a subtitle segment.",
        ),
    ] = None,
    clip_timestamps: Annotated[
        str,
        typer.Option(
            "--clip-timestamps",
            "--clip_timestamps",
            help="Comma-separated start,end timestamps in seconds to process.",
        ),
    ] = DEFAULT_CLIP_TIMESTAMPS,
    hallucination_silence_threshold: Annotated[
        Optional[float],
        typer.Option(
            "--hallucination-silence-threshold",
            "--hallucination_silence_threshold",
            min=0.0,
            help="Skip long silent periods around possible hallucinations.",
        ),
    ] = DEFAULT_HALLUCINATION_SILENCE_THRESHOLD,
    return_candidates: Annotated[
        bool,
        typer.Option(
            "--return-candidates/--no-return-candidates",
            help="Include ranked decoding candidates in JSON output.",
        ),
    ] = DEFAULT_RETURN_CANDIDATES,
) -> None:
    require_binary("ffmpeg")
    output_dir.mkdir(parents=True, exist_ok=True)

    if output_name and len(audio) > 1:
        raise typer.BadParameter("--output-name can only be used with one audio input")

    try:
        temperature_fallback_increment = (
            None
            if temperature_increment_on_fallback == 0
            else temperature_increment_on_fallback
        )
        temperature_schedule_value = temperature_schedule(
            temperature,
            temperature_fallback_increment,
        )
        output_formats(output_format)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    writer_options = validate_writer_options(
        word_timestamps=word_timestamps,
        highlight_words=highlight_words,
        max_line_width=max_line_width,
        max_line_count=max_line_count,
        max_words_per_line=max_words_per_line,
    )

    decode_options = {
        "task": task.value,
        "language": language,
        "verbose": verbose,
        "temperature": temperature_schedule_value,
        "best_of": best_of,
        "beam_size": beam_size,
        "patience": patience,
        "length_penalty": length_penalty,
        "suppress_tokens": suppress_tokens,
        "initial_prompt": initial_prompt,
        "condition_on_previous_text": condition_on_previous_text,
        "fp16": fp16,
        "compression_ratio_threshold": compression_ratio_threshold,
        "logprob_threshold": logprob_threshold,
        "no_speech_threshold": no_speech_threshold,
        "word_timestamps": word_timestamps,
        "prepend_punctuations": prepend_punctuations,
        "append_punctuations": append_punctuations,
        "clip_timestamps": clip_timestamps,
        "hallucination_silence_threshold": hallucination_silence_threshold,
        "return_candidates": return_candidates,
    }

    failures = 0
    for audio_arg in audio:
        try:
            written_paths = transcribe_one(
                audio_arg,
                model=model,
                output_dir=output_dir,
                output_name=output_name,
                output_format=output_format,
                verbose=verbose,
                decode_options=decode_options,
                writer_options=writer_options,
            )
        except Exception as error:
            console.print_exception(show_locals=False)
            console.print(
                f"[red]Skipping[/red] {audio_arg} due to "
                f"{type(error).__name__}: {error}"
            )
            failures += 1
        else:
            for path in written_paths:
                console.print(f"[green]Wrote[/green] {path}")

    if failures:
        raise typer.Exit(1)
