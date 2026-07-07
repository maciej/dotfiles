from __future__ import annotations

import shlex
import subprocess
from typing import Sequence

from . import state
from .core import ensure_user_local_bin_on_path, log, log_err, uname
from .errors import InstallerError, InstallerUsageError
from .options import (
    Options,
    apply_local_install_default,
    parse_args,
    print_help,
    update_local_install_default_marker,
    validate_install_mode_options,
)
from .package_managers import (
    ensure_brew,
    ensure_macos_command_line_tools,
    install_apt_packages,
    install_brew_casks,
    install_brew_k8s_packages,
    install_brew_packages,
    install_uv_tools,
    is_debian_apt_host,
)
from .shell_setup import finish_stow_and_shell_setup
from .terminfo import install_ghostty_terminfo, remove_legacy_ghostty_config_macos
from .tools import (
    install_bat_local,
    install_codex_cli_local,
    install_git_delta_linux,
    install_git_delta_local,
    install_helix_linux,
    install_helix_local,
    install_kubectl_linux_local,
    install_kubie_linux_local,
)


def local_install(options: Options) -> None:
    ensure_user_local_bin_on_path()
    install_bat_local()
    install_git_delta_local()
    install_helix_local()
    install_codex_cli_local()
    finish_stow_and_shell_setup(options)


def install_k8s_tools() -> None:
    os_name = uname("-s")
    if os_name == "Darwin":
        install_brew_k8s_packages()
    elif os_name == "Linux":
        install_kubectl_linux_local()
        install_kubie_linux_local()
    else:
        log(f"Unsupported host for optional k8s tool group ({os_name or 'unknown'}); skipping k8s tools")


def install_optional_tool_groups(options: Options) -> None:
    for group in options.with_groups:
        if group == "k8s":
            install_k8s_tools()
        else:
            raise InstallerError(f"Unknown optional tool group reached installer: {group}")


def main_install(options: Options) -> None:
    if options.local_install:
        local_install(options)
        return

    ensure_user_local_bin_on_path()
    os_name = uname("-s")

    if os_name == "Darwin":
        ensure_macos_command_line_tools()
        ensure_brew()
        install_brew_packages()
        install_optional_tool_groups(options)
        install_brew_casks()
        remove_legacy_ghostty_config_macos()
    elif is_debian_apt_host():
        install_apt_packages()
        install_git_delta_linux()
        install_helix_linux()
        install_optional_tool_groups(options)
    else:
        log(f"Unsupported package manager on host ({os_name or 'unknown'}); skipping package installation")
        install_optional_tool_groups(options)

    install_uv_tools()
    install_ghostty_terminfo()
    finish_stow_and_shell_setup(options)


def run_cli(argv: Sequence[str]) -> int:
    try:
        options = parse_args(argv)
        state.CURRENT_OPTIONS = options
        validate_install_mode_options(options)
        apply_local_install_default(options)
        update_local_install_default_marker(options)
        main_install(options)
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except InstallerUsageError as exc:
        log_err(str(exc))
        print_help()
        return 1
    except InstallerError as exc:
        log_err(str(exc))
        return 1
    except subprocess.CalledProcessError as exc:
        command = " ".join(shlex.quote(str(part)) for part in exc.cmd)
        log_err(f"Command failed ({exc.returncode}): {command}")
        if exc.stderr:
            log_err(exc.stderr.strip())
        return exc.returncode or 1
