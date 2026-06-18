from __future__ import annotations

import platform
import shutil
from pathlib import Path

import typer


APT_PACKAGES = {
    "ffmpeg": "ffmpeg",
    "yt-dlp": "yt-dlp",
}
BREW_PACKAGES = {
    "ffmpeg": "ffmpeg",
    "yt-dlp": "yt-dlp",
}


def os_release_values(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    values: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if not separator:
            continue
        values[key] = value.strip().strip('"')
    return values


def is_debian_like(os_release: dict[str, str] | None = None) -> bool:
    values = os_release_values() if os_release is None else os_release
    family = " ".join(
        value.lower() for value in (values.get("ID"), values.get("ID_LIKE")) if value
    )
    return any(name in family.split() for name in ("debian", "ubuntu", "raspbian"))


def install_hint(name: str, *, system: str | None = None) -> str:
    detected_system = platform.system() if system is None else system

    if detected_system == "Darwin" and name in BREW_PACKAGES:
        return f"Install it with: brew install {BREW_PACKAGES[name]}"

    if detected_system == "Linux" and name in APT_PACKAGES and is_debian_like():
        return f"Install it with: sudo apt update && sudo apt install {APT_PACKAGES[name]}"

    return f"Install {name} with your system package manager."


def require_binary(name: str, hint: str | None = None) -> None:
    if shutil.which(name) is None:
        install = install_hint(name) if hint is None else hint
        raise typer.BadParameter(
            f"{name} is required but was not found on PATH. {install}"
        )
