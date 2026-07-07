from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def log(message: str) -> None:
    print(f"[dotfiles] {message}")


def log_err(message: str) -> None:
    print(f"[dotfiles] {message}", file=sys.stderr)


def home_dir() -> Path:
    return Path(os.environ["HOME"]).expanduser()


def run(
    args: Sequence[str | Path],
    *,
    check: bool = True,
    capture: bool = False,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [str(arg) for arg in args]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    result = subprocess.run(
        command,
        check=False,
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        input=input_text,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def uname(flag: str) -> str:
    result = run(["uname", flag], check=False, capture=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def ensure_user_local_bin_on_path() -> None:
    user_bin = str(home_dir() / ".local/bin")
    path = os.environ.get("PATH", "")
    parts = path.split(os.pathsep) if path else []
    if user_bin not in parts:
        os.environ["PATH"] = os.pathsep.join([user_bin, *parts])


def resolve_uv_bin() -> str | None:
    if uv_bin := shutil.which("uv"):
        return uv_bin

    local_uv = home_dir() / ".local/bin/uv"
    if is_executable(local_uv):
        return str(local_uv)

    return None


def path_is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
