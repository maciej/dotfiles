from __future__ import annotations

import contextlib
import html
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import typer
from system_dependencies import require_binary
from whisper_memory import require_whisper_model_memory
from rich.console import Console
from rich.markdown import Markdown
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


SUMMARY_MODEL = "gpt-5.4-mini"
WHISPER_TRANSCRIBE_MODEL = "mlx-community/whisper-large-v3-turbo"
WHISPER_TRANSLATE_MODEL = "mlx-community/whisper-medium-mlx"
CACHE_NAMESPACE = "yt-summarize"
DEFAULT_MAX_RENDER_WIDTH = 120
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

app = typer.Typer(
    add_completion=False,
    help="Summarize a YouTube URL using captions first, then local MLX Whisper.",
)
console = Console(stderr=True)


class SummarySize(str, Enum):
    s = "s"
    m = "m"
    long = "l"
    xl = "xl"


class WhisperTask(str, Enum):
    transcribe = "transcribe"
    translate = "translate"


def run(
    command: list[str],
    *,
    cwd: Optional[Path] = None,
    input_text: Optional[str] = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        check=check,
        capture_output=True,
        text=True,
    )


def load_info(url: str) -> dict:
    result = run(["yt-dlp", "--dump-single-json", "--skip-download", url])
    return json.loads(result.stdout)


def read_json_dict(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        console.print(f"[yellow]Ignoring unreadable cached metadata[/yellow] {path}: {error}")
        return None
    if not isinstance(data, dict):
        console.print(f"[yellow]Ignoring non-object cached metadata[/yellow] {path}")
        return None
    return data


def default_cache_dir() -> Path:
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / CACHE_NAMESPACE
    return Path.home() / ".cache" / CACHE_NAMESPACE


def cache_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return slug or "default"


def normalize_youtube_video_id(value: str) -> Optional[str]:
    video_id = value.strip()
    if YOUTUBE_VIDEO_ID_RE.fullmatch(video_id):
        return video_id
    return None


def youtube_video_id_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host.removeprefix(prefix)

    if host in {"youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        if parsed.path == "/watch":
            video_ids = parse_qs(parsed.query).get("v") or []
            if video_ids:
                return normalize_youtube_video_id(video_ids[0])

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"embed", "live", "shorts", "v"}:
            return normalize_youtube_video_id(path_parts[1])

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
        return normalize_youtube_video_id(video_id)

    return None


def video_cache_key(info: dict, url: str) -> str:
    return cache_slug(str(info.get("id") or url))


def summary_cache_path_from_key(video_key: str, model: str, size: SummarySize, cache_dir: Path) -> Path:
    model_slug = cache_slug(model)
    return cache_dir / f"{cache_slug(video_key)}-{model_slug}-{size.value}.md"


def summary_cache_path(info: dict, url: str, model: str, size: SummarySize, cache_dir: Path) -> Path:
    return summary_cache_path_from_key(video_cache_key(info, url), model, size, cache_dir)


def transcript_cache_path_from_key(video_key: str, cache_dir: Path) -> Path:
    return cache_dir / f"{cache_slug(video_key)}-transcript.en.txt"


def transcript_cache_path(info: dict, url: str, cache_dir: Path) -> Path:
    return transcript_cache_path_from_key(video_cache_key(info, url), cache_dir)


def metadata_cache_path_from_key(video_key: str, cache_dir: Path) -> Path:
    return cache_dir / f"{cache_slug(video_key)}-metadata.json"


def metadata_cache_path(info: dict, url: str, cache_dir: Path) -> Path:
    return metadata_cache_path_from_key(video_cache_key(info, url), cache_dir)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(text + "\n", encoding="utf-8")
    temp_path.replace(path)


def write_json_atomic(path: Path, data: dict) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, sort_keys=True))


def load_info_with_cache(
    url: str,
    cache_dir: Path,
    *,
    use_cache: bool,
    refresh_cache: bool,
) -> dict:
    video_id = youtube_video_id_from_url(url)
    if use_cache and not refresh_cache and video_id:
        cached_metadata_path = metadata_cache_path_from_key(video_id, cache_dir)
        if cached_metadata_path.exists():
            cached_info = read_json_dict(cached_metadata_path)
            if cached_info is not None:
                console.print(f"[green]Using cached metadata[/green] {cached_metadata_path}")
                return cached_info

    require_binary("yt-dlp")
    info = load_info(url)

    if use_cache:
        cached_metadata_path = metadata_cache_path(info, url, cache_dir)
        write_json_atomic(cached_metadata_path, info)
        console.print(f"[green]Cached metadata[/green] {cached_metadata_path}")

    return info


def terminal_width(width_override: Optional[int] = None) -> int:
    if width_override is not None:
        return width_override
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(20, min(columns - 1, DEFAULT_MAX_RENDER_WIDTH))


def is_rich_tty() -> bool:
    return sys.stdout.isatty()


def collapse_extra_blank_lines(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    in_fence = False
    blank_run = 0

    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            blank_run = 0
            output.append(line)
            continue
        if in_fence:
            blank_run = 0
            output.append(line)
            continue
        if not line.strip():
            blank_run += 1
            if blank_run == 1:
                output.append("")
            continue
        blank_run = 0
        output.append(line)

    return "\n".join(output)


def inline_reference_style_links(markdown: str) -> str:
    lines = markdown.splitlines()
    definitions: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^\s*\[([^\]]+)\]:\s*(\S+)\s*$", line)
        if match:
            definitions[match.group(1).strip().lower()] = match.group(2).strip()
    if not definitions:
        return markdown

    used: set[str] = set()

    def replace_reference(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        reference = match.group(2).strip()
        key = (reference or label).lower()
        url = definitions.get(key)
        if not url:
            return match.group(0)
        used.add(key)
        return f"[{label}]({url})"

    inlined = re.sub(r"\[([^\]]+)\]\[([^\]]*)\]", replace_reference, markdown)
    if not used:
        return inlined

    kept_lines: list[str] = []
    for line in inlined.splitlines():
        match = re.match(r"^\s*\[([^\]]+)\]:\s*(\S+)\s*$", line)
        if match and match.group(1).strip().lower() in used:
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def materialize_inline_markdown_links(markdown: str) -> str:
    output: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            output.append(line)
            continue
        if in_fence:
            output.append(line)
            continue

        def replace_link(match: re.Match[str]) -> str:
            label = match.group(1).strip()
            url = match.group(2).strip()
            if not label or not url:
                return match.group(0)
            return f"{label}: {url}"

        output.append(re.sub(r"(?<!!)\[([^\]]+)\]\((\S+?)\)", replace_link, line))
    return "\n".join(output)


def prepare_markdown_for_terminal(markdown: str) -> str:
    return collapse_extra_blank_lines(
        materialize_inline_markdown_links(inline_reference_style_links(markdown))
    )


def print_summary(summary: str, *, plain: bool, width: Optional[int]) -> None:
    if not plain and is_rich_tty():
        output_console = Console(width=terminal_width(width), soft_wrap=False)
        output_console.print(Markdown(prepare_markdown_for_terminal(summary), hyperlinks=True))
        return

    sys.stdout.write(summary.lstrip("\n"))
    if not summary.endswith("\n"):
        sys.stdout.write("\n")


def emit_cached_summary(
    cache_path: Path,
    cached_transcript_path: Path,
    *,
    output_path: Optional[Path],
    transcript_output: Optional[Path],
    overwrite: bool,
    plain: bool,
    width: Optional[int],
) -> bool:
    if not cache_path.exists():
        return False

    summary = cache_path.read_text(encoding="utf-8").strip()
    console.print(f"[green]Using cached summary[/green] {cache_path}")
    print_summary(summary, plain=plain, width=width)

    if transcript_output:
        if transcript_output.exists() and not overwrite:
            console.print(
                f"[yellow]Transcript output already exists; leaving it unchanged[/yellow] {transcript_output}"
            )
        elif cached_transcript_path.exists():
            transcript_output.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(
                transcript_output,
                cached_transcript_path.read_text(encoding="utf-8").strip(),
            )
            console.print(f"[green]Wrote transcript[/green] {transcript_output}")
        else:
            console.print(
                f"[yellow]No cached transcript available for --transcript-output[/yellow] {cached_transcript_path}"
            )

    if output_path:
        if output_path.exists() and not overwrite:
            console.print(f"[yellow]Output already exists; leaving it unchanged[/yellow] {output_path}")
            return True
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(output_path, summary)
        console.print(f"[green]Wrote summary[/green] {output_path}")

    return True


def is_english_language(language: str) -> bool:
    normalized = language.lower()
    return normalized == "en" or normalized.startswith("en-")


def english_caption_candidates(info: dict) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}

    for language in sorted(subtitles):
        if is_english_language(language):
            candidates.append((language, "manual"))
    for language in sorted(automatic):
        if is_english_language(language):
            candidates.append((language, "auto"))
    return candidates


def original_caption_candidates(info: dict) -> list[tuple[str, str]]:
    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    candidates: list[tuple[str, str]] = []

    for language in sorted(subtitles):
        if not is_english_language(language):
            candidates.append((language, "manual"))

    for language in sorted(automatic):
        if language.endswith("-orig") and not is_english_language(language):
            candidates.append((language, "auto"))

    info_language = info.get("language")
    if info_language and not is_english_language(info_language):
        for source in ("manual", "auto"):
            if (info_language, source) not in candidates:
                source_map = subtitles if source == "manual" else automatic
                if info_language in source_map:
                    candidates.append((info_language, source))

    return candidates


def caption_glob_name(video_id: str, language: str) -> str:
    return f"{video_id}.{language}.*"


def download_caption(url: str, video_id: str, language: str, source: str, work_dir: Path) -> Optional[Path]:
    for existing in work_dir.glob(caption_glob_name(video_id, language)):
        existing.unlink()

    command = [
        "yt-dlp",
        "--skip-download",
        "--sub-langs",
        language,
        "--sub-format",
        "json3/vtt/best",
        "-o",
        str(work_dir / "%(id)s.%(ext)s"),
    ]
    command.append("--write-subs" if source == "manual" else "--write-auto-subs")
    command.append(url)

    result = run(command, check=False)
    if result.returncode != 0:
        if result.stderr.strip():
            console.print(result.stderr.strip())
        return None

    caption_files = sorted(work_dir.glob(caption_glob_name(video_id, language)))
    return caption_files[0] if caption_files else None


def normalize_transcript(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_from_json3(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[str] = []
    for event in data.get("events", []):
        text = "".join(segment.get("utf8", "") for segment in event.get("segs", []))
        text = text.replace("\n", " ").strip()
        if text:
            chunks.append(text)
    return normalize_transcript(" ".join(chunks))


def text_from_vtt(path: Path) -> str:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if (
            not line
            or line.startswith("WEBVTT")
            or line.startswith("Kind:")
            or line.startswith("Language:")
            or "-->" in line
        ):
            continue
        line = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
        line = re.sub(r"</?c[^>]*>", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        line = normalize_transcript(line)
        if not line:
            continue
        if lines and (line == lines[-1] or lines[-1].startswith(line + " ")):
            continue
        if lines and line.startswith(lines[-1] + " "):
            lines[-1] = line
            continue
        lines.append(line)
    return normalize_transcript("\n".join(lines))


def extract_caption_text(path: Path) -> str:
    if path.suffix == ".json3":
        return text_from_json3(path)
    if path.suffix == ".vtt":
        return text_from_vtt(path)
    return normalize_transcript(path.read_text(encoding="utf-8"))


def find_caption_transcript(
    url: str,
    info: dict,
    work_dir: Path,
    *,
    prefer_original: bool,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    video_id = info.get("id") or "video"
    groups = []
    if not prefer_original:
        groups.append(("English captions", english_caption_candidates(info), "en"))
    groups.append(("original captions", original_caption_candidates(info), "source"))

    for label, candidates, transcript_language in groups:
        if not candidates:
            continue
        for language, source in candidates:
            console.print(f"[cyan]Trying {label}[/cyan]: {language} ({source})")
            path = download_caption(url, video_id, language, source, work_dir)
            if path is None:
                continue
            text = extract_caption_text(path)
            if len(text.split()) < 20:
                console.print(f"[yellow]Ignoring empty or tiny caption track[/yellow]: {path.name}")
                continue
            return text, transcript_language, f"{language} {source} captions"

    return None, None, None


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
        result = run(command)
        duration = float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None
    return duration if duration > 0 else None


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


def download_audio(url: str, work_dir: Path) -> Path:
    output_template = str(work_dir / "%(id)s.%(ext)s")
    command = [
        "yt-dlp",
        "-f",
        "ba/b",
        "-o",
        output_template,
        url,
    ]
    result = run(command, check=False)
    if result.returncode != 0:
        if result.stderr.strip():
            console.print(result.stderr.strip())
        raise typer.Exit(result.returncode)

    media_files = [
        path
        for path in work_dir.iterdir()
        if path.is_file() and path.suffix not in {".json", ".json3", ".vtt", ".txt", ".md"}
    ]
    if not media_files:
        raise typer.BadParameter("yt-dlp did not produce an audio/video file.")
    return max(media_files, key=lambda path: path.stat().st_mtime)


def extract_audio(
    media: Path,
    audio: Path,
    *,
    progress: Progress,
    task_id: TaskID,
    duration: Optional[float],
) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-progress",
        "pipe:1",
        "-y",
        "-i",
        str(media),
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
                "Running mlx-whisper locally...",
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


def whisper_transcript(
    url: str,
    work_dir: Path,
    *,
    task: WhisperTask,
    language: Optional[str],
    transcribe_model: str,
    translate_model: str,
) -> tuple[str, str]:
    model = translate_model if task == WhisperTask.translate else transcribe_model

    if task == WhisperTask.translate and "turbo" in model.lower():
        console.print(
            "[yellow]Whisper turbo is not trained for translation; consider --whisper-translate-model "
            f"{WHISPER_TRANSLATE_MODEL}.[/yellow]"
        )

    require_whisper_model_memory(model)
    require_binary("ffmpeg")
    media = download_audio(url, work_dir)
    duration = get_media_duration(media)
    audio = work_dir / f"{media.stem}.wav"

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
        extract_task = progress.add_task("Extracting audio with ffmpeg...", total=duration)
        extract_audio(media, audio, progress=progress, task_id=extract_task, duration=duration)
        progress.update(
            extract_task,
            description="Audio extracted",
            completed=duration if duration is not None else None,
        )

        transcribe_module = importlib.import_module("mlx_whisper.transcribe")
        original_tqdm = transcribe_module.tqdm.tqdm
        transcribe_module.tqdm.tqdm = rich_tqdm_factory(progress)

        decode_options = {
            "task": task.value,
            "language": language,
            "verbose": False,
        }
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = transcribe_module.transcribe(
                    str(audio),
                    path_or_hf_repo=model,
                    **decode_options,
                )
        finally:
            transcribe_module.tqdm.tqdm = original_tqdm

    text = normalize_transcript(str(result.get("text", "")))
    if len(text.split()) < 20:
        raise typer.BadParameter("mlx-whisper did not produce enough transcript text.")
    return text, f"mlx-whisper {task.value} ({model})"


def size_instruction(size: SummarySize) -> str:
    return {
        SummarySize.s: "Write a concise 1 paragraph summary, about 100-150 words.",
        SummarySize.m: "Write a clear 2 paragraph summary, about 250-350 words.",
        SummarySize.long: "Write a detailed 4-6 paragraph summary with the main claims, evidence, and implications.",
        SummarySize.xl: "Write an extensive structured summary with sections for context, key points, details, and takeaways.",
    }[size]


def codex_exec(prompt: str, model: str, work_dir: Path, output_path: Path) -> str:
    command = [
        "codex",
        "exec",
        "--model",
        model,
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
        "--output-last-message",
        str(output_path),
        "-",
    ]
    result = run(command, cwd=work_dir, input_text=prompt, check=False)
    if result.returncode != 0:
        if result.stderr.strip():
            console.print(result.stderr.strip())
        raise typer.Exit(result.returncode)
    return output_path.read_text(encoding="utf-8").strip()


def translate_to_english(text: str, model: str, work_dir: Path) -> str:
    prompt = f"""Translate the transcript below into natural English.

Keep factual content intact. Preserve names, product names, and technical terms.
Return only the English translation.

<transcript>
{text}
</transcript>
"""
    return codex_exec(prompt, model, work_dir, work_dir / "translation.md")


def format_yyyymmdd(value: object) -> Optional[str]:
    if not value:
        return None
    text = str(value)
    if re.fullmatch(r"\d{8}", text):
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def format_count(value: object) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def clean_metadata_text(value: object, *, max_chars: int) -> Optional[str]:
    if not value:
        return None
    text = normalize_transcript(str(value))
    if len(text) <= max_chars:
        return text
    truncated = text[: max_chars - 1].rsplit(" ", 1)[0].rstrip()
    return f"{truncated}..."


def format_list(values: object, *, limit: int = 12) -> Optional[str]:
    if not isinstance(values, list):
        return None
    items = [str(value).strip() for value in values if str(value).strip()]
    if not items:
        return None
    suffix = f", +{len(items) - limit} more" if len(items) > limit else ""
    return ", ".join(items[:limit]) + suffix


def format_chapter_time(seconds: object) -> Optional[str]:
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return None
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_chapters(chapters: object, *, limit: int = 20) -> Optional[str]:
    if not isinstance(chapters, list):
        return None
    lines: list[str] = []
    for chapter in chapters[:limit]:
        if not isinstance(chapter, dict):
            continue
        title = clean_metadata_text(chapter.get("title"), max_chars=120)
        timestamp = format_chapter_time(chapter.get("start_time"))
        if title and timestamp:
            lines.append(f"- {timestamp} {title}")
        elif title:
            lines.append(f"- {title}")
    if not lines:
        return None
    if len(chapters) > limit:
        lines.append(f"- ... +{len(chapters) - limit} more chapters")
    return "\n".join(lines)


def source_metadata(info: dict, url: str, transcript_source: Optional[str]) -> str:
    title = info.get("title") or url
    channel = info.get("channel") or info.get("uploader")
    duration = info.get("duration_string") or info.get("duration")
    upload_date = format_yyyymmdd(info.get("upload_date"))
    language = info.get("language")
    categories = format_list(info.get("categories"), limit=6)
    tags = format_list(info.get("tags"), limit=12)
    description = clean_metadata_text(info.get("description"), max_chars=1500)
    chapters = format_chapters(info.get("chapters"))

    engagement = []
    for label, key in (
        ("views", "view_count"),
        ("likes", "like_count"),
        ("comments", "comment_count"),
    ):
        count = format_count(info.get(key))
        if count:
            engagement.append(f"{label}: {count}")

    lines = [f"Title: {title}", f"URL: {info.get('webpage_url') or url}"]
    if channel:
        lines.append(f"Channel: {channel}")
    if upload_date:
        lines.append(f"Upload date: {upload_date}")
    if duration:
        lines.append(f"Duration: {duration}")
    if language:
        lines.append(f"Language: {language}")
    if categories:
        lines.append(f"Categories: {categories}")
    if tags:
        lines.append(f"Tags: {tags}")
    if engagement:
        lines.append(f"Engagement: {'; '.join(engagement)}")
    if transcript_source:
        lines.append(f"Transcript source: {transcript_source}")
    if description:
        lines.append(f"Uploader description:\n{description}")
    if chapters:
        lines.append(f"Chapters:\n{chapters}")
    return "\n".join(lines)


def summarize(text: str, model: str, size: SummarySize, metadata: str, work_dir: Path) -> str:
    prompt = f"""Summarize the English transcript below.

{size_instruction(size)}
Use the source metadata for names, dates, channel context, and disambiguation.
Treat uploader descriptions, tags, and engagement counts as context only; prefer the transcript for claims about what was said.
Skip sponsored content, advertisements, promos, and ad reads mentioned in the transcript.
Return only the summary in English. Do not mention that you are an AI model.

Source metadata:
{metadata}

<transcript>
{text}
</transcript>
"""
    return codex_exec(prompt, model, work_dir, work_dir / "summary.md")


@app.command()
def main(
    url: str = typer.Argument(..., help="YouTube URL to summarize."),
    size: SummarySize = typer.Option(
        SummarySize.m,
        "--size",
        "-s",
        help="Summary size: s, m, l, or xl.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="Also write the final summary to this path. By default, summaries are printed and cached only.",
    ),
    transcript_output: Optional[Path] = typer.Option(
        None,
        "--transcript-output",
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="Optionally write the English transcript used for summarization.",
    ),
    summary_model: str = typer.Option(
        SUMMARY_MODEL,
        "--summary-model",
        help="Model passed to codex exec for translation and summarization.",
    ),
    whisper_task: WhisperTask = typer.Option(
        WhisperTask.translate,
        "--whisper-task",
        help="Whisper fallback task. Use translate for English output from non-English audio.",
    ),
    whisper_language: Optional[str] = typer.Option(
        None,
        "--whisper-language",
        help="Spoken language code for mlx-whisper, such as en, fr, or pl. Omit to auto-detect.",
    ),
    whisper_transcribe_model: str = typer.Option(
        WHISPER_TRANSCRIBE_MODEL,
        "--whisper-transcribe-model",
        help="MLX Whisper model for --whisper-task transcribe.",
    ),
    whisper_translate_model: str = typer.Option(
        WHISPER_TRANSLATE_MODEL,
        "--whisper-translate-model",
        help="MLX Whisper model for --whisper-task translate.",
    ),
    prefer_whisper: bool = typer.Option(
        False,
        "--prefer-whisper",
        help="Skip caption lookup and use local mlx-whisper.",
    ),
    keep_work: bool = typer.Option(
        False,
        "--keep-work",
        help="Keep the temporary working directory for debugging.",
    ),
    use_cache: bool = typer.Option(
        True,
        "--cache/--no-cache",
        help="Read and write plain Markdown summaries in the XDG cache directory.",
    ),
    refresh_cache: bool = typer.Option(
        False,
        "--refresh-cache",
        help="Ignore any existing cached summary and replace it after summarizing.",
    ),
    cache_dir: Optional[Path] = typer.Option(
        None,
        "--cache-dir",
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
        help="Cache directory. Defaults to ${XDG_CACHE_HOME:-~/.cache}/yt-summarize.",
    ),
    plain: bool = typer.Option(
        False,
        "--plain",
        help="Keep raw Markdown output in the terminal instead of rendering it.",
    ),
    width: Optional[int] = typer.Option(
        None,
        "--width",
        min=20,
        help="Override terminal width for Markdown rendering. Defaults to auto-detect, capped at 120.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing summary/transcript output files.",
    ),
) -> None:
    output_path = output.with_suffix(".md") if output else None
    resolved_cache_dir = cache_dir or default_cache_dir()

    if use_cache and not refresh_cache:
        video_id = youtube_video_id_from_url(url)
        if video_id:
            cache_path = summary_cache_path_from_key(video_id, summary_model, size, resolved_cache_dir)
            cached_transcript_path = transcript_cache_path_from_key(video_id, resolved_cache_dir)
            if emit_cached_summary(
                cache_path,
                cached_transcript_path,
                output_path=output_path,
                transcript_output=transcript_output,
                overwrite=overwrite,
                plain=plain,
                width=width,
            ):
                return

    require_binary("codex", "Install the Codex CLI and make sure it is on PATH.")

    temp_context: Optional[tempfile.TemporaryDirectory[str]] = None
    if keep_work:
        work_dir = Path(tempfile.mkdtemp(prefix="yt-summarize-"))
    else:
        temp_context = tempfile.TemporaryDirectory(prefix="yt-summarize-")
        work_dir = Path(temp_context.name)

    try:
        info = load_info_with_cache(
            url,
            resolved_cache_dir,
            use_cache=use_cache,
            refresh_cache=refresh_cache,
        )
        title = info.get("title") or url
        duration = info.get("duration_string") or info.get("duration") or "unknown"
        channel = info.get("channel") or info.get("uploader") or "unknown"
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path = summary_cache_path(info, url, summary_model, size, resolved_cache_dir)
        cached_transcript_path = transcript_cache_path(info, url, resolved_cache_dir)
        cached_metadata_path = metadata_cache_path(info, url, resolved_cache_dir)

        if use_cache and not refresh_cache and emit_cached_summary(
            cache_path,
            cached_transcript_path,
            output_path=output_path,
            transcript_output=transcript_output,
            overwrite=overwrite,
            plain=plain,
            width=width,
        ):
            return

        if output_path and output_path.exists() and not overwrite:
            raise typer.BadParameter(
                f"{output_path} already exists. Pass --overwrite to replace it."
            )
        if transcript_output and transcript_output.exists() and not overwrite:
            raise typer.BadParameter(
                f"{transcript_output} already exists. Pass --overwrite to replace it."
            )

        panel_body = "\n".join(
            [
                f"[bold]{title}[/bold]",
                f"channel: {channel}",
                f"duration: {duration}",
                f"size: {size.value}",
                f"model: [cyan]{summary_model}[/cyan]",
                f"summary cache: {cache_path if use_cache else 'disabled'}",
                f"transcript cache: {cached_transcript_path if use_cache else 'disabled'}",
                f"metadata cache: {cached_metadata_path if use_cache else 'disabled'}",
            ]
        )
        console.print(Panel.fit(panel_body, title="yt-summarize"))

        transcript: Optional[str] = None
        transcript_language: Optional[str] = None
        source: Optional[str] = None
        transcript_from_cache = False

        if use_cache and not refresh_cache and not prefer_whisper and cached_transcript_path.exists():
            transcript = cached_transcript_path.read_text(encoding="utf-8").strip()
            transcript_language = "en"
            source = f"cached English transcript ({cached_transcript_path})"
            transcript_from_cache = True
            console.print(f"[green]Using cached transcript[/green] {cached_transcript_path}")

        if transcript is None and not prefer_whisper:
            require_binary("yt-dlp")
            transcript, transcript_language, source = find_caption_transcript(
                url,
                info,
                work_dir,
                prefer_original=False,
            )

        if transcript is None:
            if prefer_whisper:
                require_binary("yt-dlp")
            console.print("[cyan]No usable captions found; falling back to mlx-whisper.[/cyan]")
            transcript, source = whisper_transcript(
                url,
                work_dir,
                task=whisper_task,
                language=whisper_language,
                transcribe_model=whisper_transcribe_model,
                translate_model=whisper_translate_model,
            )
            transcript_language = "en" if whisper_task == WhisperTask.translate else "source"

        if transcript_language != "en":
            console.print("[cyan]Translating transcript to English with codex exec...[/cyan]")
            transcript = translate_to_english(transcript, summary_model, work_dir)
            source = f"{source}; translated with codex exec"

        if use_cache and not transcript_from_cache:
            write_text_atomic(cached_transcript_path, transcript)
            console.print(f"[green]Cached transcript[/green] {cached_transcript_path}")

        if transcript_output:
            transcript_output.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(transcript_output, transcript)
            console.print(f"[green]Wrote transcript[/green] {transcript_output}")

        console.print("[cyan]Summarizing with codex exec...[/cyan]")
        summary = summarize(
            transcript,
            summary_model,
            size,
            source_metadata(info, url, source),
            work_dir,
        )
        if use_cache:
            write_text_atomic(cache_path, summary)
            console.print(f"[green]Cached summary[/green] {cache_path}")
        print_summary(summary, plain=plain, width=width)
        if output_path:
            write_text_atomic(output_path, summary)
            console.print(f"[green]Wrote summary[/green] {output_path}")
    finally:
        if keep_work:
            console.print(f"[yellow]Kept work dir[/yellow] {work_dir}")
        elif temp_context is not None:
            temp_context.cleanup()
