from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Sequence

from . import state
from .config import LEGACY_STOW_PATHS, PRECREATED_STOW_DIRECTORIES
from .core import command_exists, home_dir, log, path_is_inside, run
from .errors import InstallerError
from .options import Options


def home_relative_paths(paths: Sequence[str]) -> list[Path]:
    return [home_dir() / path for path in paths]


def validate_legacy_stow_targets() -> None:
    for path in home_relative_paths(LEGACY_STOW_PATHS):
        try:
            path.relative_to(home_dir())
        except ValueError as exc:
            raise InstallerError(
                f"Legacy stow target must be an absolute path under HOME: {path}"
            ) from exc

        repo_path = state.DOTFILES_DIR / path.relative_to(home_dir())
        if repo_path.exists():
            raise InstallerError(
                f"Legacy stow target is still present in the repo: {path}\n"
                "Remove it from LEGACY_STOW_PATHS or delete the repo path "
                "before rerunning install.sh."
            )


def remove_legacy_stow_targets() -> None:
    for path in home_relative_paths(LEGACY_STOW_PATHS):
        if not path.is_symlink():
            if path.exists():
                log(f"Legacy path exists but is not a symlink; leaving it in place: {path}")
            else:
                log(f"No legacy stow target found: {path}")
            continue

        link_target = os.readlink(path)
        try:
            resolved_target = resolve_symlink_target_lexically(path, link_target)
        except OSError:
            log(f"Could not resolve legacy symlink target; leaving it in place: {path}")
            continue

        if resolved_target == state.DOTFILES_DIR or path_is_inside(
            resolved_target,
            state.DOTFILES_DIR,
        ):
            path.unlink()
            log(f"Removed legacy stow target: {path}")
        else:
            log(f"Legacy path points outside this dotfiles repo; leaving it in place: {path}")


def resolve_symlink_target_lexically(link_path: Path, link_target: str) -> Path:
    target_path = Path(link_target)
    if not target_path.is_absolute():
        target_path = link_path.parent.resolve(strict=True) / target_path
    return Path(os.path.normpath(os.fspath(target_path)))


def ensure_precreated_stow_directories() -> None:
    for directory in home_relative_paths(PRECREATED_STOW_DIRECTORIES):
        if directory.is_symlink():
            log(f"Precreated stow directory is currently a symlink; leaving it in place: {directory}")
            continue
        directory.mkdir(parents=True, exist_ok=True)
        log(f"Ensured directory exists before stow: {directory}")


def ensure_ssh_config_fragment_directory() -> None:
    ssh_dir = home_dir() / ".ssh"
    include_dir = ssh_dir / "config.d"
    if ssh_dir.exists() and not ssh_dir.is_dir():
        raise InstallerError(f"SSH path exists but is not a directory: {ssh_dir}")

    include_dir.mkdir(parents=True, exist_ok=True)
    ssh_dir.chmod(0o700)
    include_dir.chmod(0o700)
    log(f"Ensured SSH config fragment directory exists: {include_dir}")


def ssh_config_has_include(config_file: Path, include_pattern: str) -> bool:
    for line in config_file.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if parts and parts[0].lower() == "include" and include_pattern in parts[1:]:
            return True
    return False


def ensure_ssh_config_include() -> None:
    ssh_dir = home_dir() / ".ssh"
    config_file = ssh_dir / "config"
    include_pattern = os.environ.get(
        "SSH_CONFIG_INCLUDE_PATTERN",
        "~/.ssh/config.d/*.conf",
    )
    include_line = f"Include {include_pattern}"

    ssh_dir.mkdir(parents=True, exist_ok=True)
    ssh_dir.chmod(0o700)

    if not config_file.exists():
        fd = os.open(config_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(f"{include_line}\n")
        log(f"Created SSH config with fragment include: {config_file}")
        return

    if not config_file.is_file():
        raise InstallerError(f"SSH config exists but is not a regular file: {config_file}")

    if ssh_config_has_include(config_file, include_pattern):
        log(f"SSH config already includes fragments: {include_pattern}")
        return

    lines = config_file.read_text().splitlines()
    insert_at = len(lines)
    for index, line in enumerate(lines):
        if re.match(r"^\s*(Host|Match)(\s|$)", line):
            insert_at = index
            break

    new_lines = [*lines[:insert_at], include_line, *lines[insert_at:]]
    config_file.write_text("\n".join(new_lines) + "\n")
    log(f"Added SSH config fragment include: {include_pattern}")


def link_dotfiles() -> None:
    if not command_exists("stow"):
        raise InstallerError("GNU Stow not installed; skipping symlink setup")

    flags = [
        "-v",
        "--no-folding",
        f"--target={home_dir()}",
        f"--dir={state.DOTFILES_DIR}",
    ]
    restow = os.environ.get("DOTFILES_STOW_RESTOW", "false")
    adopt = os.environ.get("DOTFILES_STOW_ADOPT", "false")
    if restow == "true" or adopt == "true":
        flags.append("--restow")
    if adopt == "true":
        flags.append("--adopt")
    flags.append(".")

    log("Linking dotfiles with stow")
    result = run(["stow", *flags], check=False)
    if result.returncode != 0:
        raise InstallerError(
            "Stow reported conflicts. Existing non-symlink files already "
            "exist.\nSet DOTFILES_STOW_ADOPT=true to adopt existing files "
            "into this repo, then relaunch install."
        )


def sync_zed_settings() -> None:
    script_path = state.DOTFILES_DIR / "scripts/zed-settings"
    if not script_path.is_file():
        raise InstallerError(f"Zed settings helper is missing: {script_path}")

    log("Generating live Zed settings")
    result = run([script_path, "push"], check=False)
    if result.returncode == 0:
        return
    if result.returncode == 2:
        log("Skipping Zed settings update; live file is newer")
        return
    raise InstallerError("Zed settings sync failed")


def rebuild_bat_cache() -> None:
    bat_cmd = shutil.which("bat") or shutil.which("batcat")
    if bat_cmd is None:
        log("bat is not installed; skipping bat cache rebuild")
        return

    if not (home_dir() / ".config/bat/themes").is_dir():
        log("No custom bat themes found; skipping bat cache rebuild")
        return

    log("Rebuilding bat syntax/theme cache")
    run([bat_cmd, "cache", "--build"])


def finish_stow_and_shell_setup(options: Options) -> None:
    validate_legacy_stow_targets()
    remove_legacy_stow_targets()
    ensure_precreated_stow_directories()
    ensure_ssh_config_fragment_directory()
    link_dotfiles()
    ensure_ssh_config_include()
    rebuild_bat_cache()
    if options.sync_zed_settings:
        sync_zed_settings()
    else:
        log("Skipping Zed settings sync by default; pass --sync-zed-settings to enable it")
