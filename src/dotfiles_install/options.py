from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .config import HELP_TEXT, KNOWN_WITH_GROUPS
from .core import home_dir, log
from .errors import InstallerError, InstallerUsageError


@dataclass
class Options:
    local_install: bool = False
    local_install_choice: str = "auto"
    upgrade: bool = False
    sync_zed_settings: bool = False
    with_groups: list[str] = field(default_factory=list)


def print_help() -> None:
    print(HELP_TEXT, end="")


def add_with_group(options: Options, group: str) -> None:
    if not group:
        raise InstallerUsageError("Optional tool group cannot be empty.")
    if group not in KNOWN_WITH_GROUPS:
        raise InstallerUsageError(f"Unknown optional tool group: {group}")
    if group not in options.with_groups:
        options.with_groups.append(group)


def parse_with_groups(options: Options, groups: str) -> None:
    if not groups:
        raise InstallerUsageError("--with requires an optional tool group.")
    for group in groups.split(","):
        add_with_group(options, group)


def parse_args(argv: Sequence[str]) -> Options:
    options = Options()
    index = 0

    while index < len(argv):
        arg = argv[index]
        if arg == "--local":
            options.local_install = True
            options.local_install_choice = "local"
        elif arg == "--no-local":
            options.local_install = False
            options.local_install_choice = "system"
        elif arg == "--with":
            index += 1
            if index >= len(argv):
                raise InstallerUsageError("--with requires an optional tool group.")
            parse_with_groups(options, argv[index])
        elif arg.startswith("--with="):
            parse_with_groups(options, arg.removeprefix("--with="))
        elif arg == "--upgrade":
            options.upgrade = True
        elif arg == "--sync-zed-settings":
            options.sync_zed_settings = True
        elif arg == "--help":
            print_help()
            raise SystemExit(0)
        else:
            raise InstallerUsageError(f"Unknown argument: {arg}")
        index += 1

    return options


def validate_install_mode_options(options: Options) -> None:
    if options.local_install_choice == "local" and options.with_groups:
        raise InstallerError(
            "--with installs optional system tool groups and cannot be "
            "combined with --local."
        )


def dotfiles_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", home_dir() / ".config"))


def local_install_marker_path() -> Path:
    return dotfiles_config_home() / "dotfiles/install-mode"


def clear_local_install_default() -> None:
    marker = local_install_marker_path()
    if not marker.exists() and not marker.is_symlink():
        return
    if not marker.is_file() and not marker.is_symlink():
        raise InstallerError(
            f"Local install marker exists but is not a regular file: {marker}"
        )

    marker.unlink()
    log(f"Cleared local install default marker: {marker}")


def remember_local_install_default() -> None:
    marker = local_install_marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("local\n")
    marker.chmod(0o644)
    log(f"Remembered local install default in {marker}")


def apply_local_install_default(options: Options) -> None:
    marker = local_install_marker_path()

    if options.local_install_choice == "local":
        options.local_install = True
    elif options.local_install_choice == "system":
        options.local_install = False
    elif marker.is_file():
        if options.with_groups:
            log(f"Ignoring local install default for this optional tool group install: {marker}")
        else:
            options.local_install = True
            log(f"Defaulting to --local because {marker} exists")


def update_local_install_default_marker(options: Options) -> None:
    if options.local_install_choice == "local":
        remember_local_install_default()
    elif options.local_install_choice == "system":
        clear_local_install_default()
