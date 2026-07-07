from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Sequence

from . import state
from .config import (
    APT_OPTIONAL_PACKAGES,
    APT_PACKAGES,
    BREW_CASKS,
    BREW_K8S_PACKAGES,
    BREW_PACKAGES,
    UV_TOOL_PACKAGES,
)
from .core import (
    command_exists,
    ensure_user_local_bin_on_path,
    is_executable,
    log,
    log_err,
    resolve_uv_bin,
    run,
    uname,
)
from .errors import InstallerError


def ensure_macos_command_line_tools() -> None:
    if uname("-s") != "Darwin":
        return

    if not command_exists("xcode-select"):
        raise InstallerError(
            "xcode-select is missing. Install Xcode Command Line Tools "
            "manually, then rerun this installer."
        )

    if run(["xcode-select", "-p"], check=False, capture=True).returncode == 0:
        log("Xcode Command Line Tools already available")
        return

    log("Xcode Command Line Tools are required before bootstrapping dotfiles")
    result = run(
        ["xcode-select", "--install"],
        check=False,
        capture=True,
    )
    output = f"{result.stdout or ''}\n{result.stderr or ''}"
    if result.returncode == 0 or re.search(
        "install requested|already installed|currently being installed",
        output,
        flags=re.IGNORECASE,
    ):
        raise InstallerError(
            "Complete the Xcode Command Line Tools installer, then rerun "
            "this installer."
        )

    raise InstallerError(
        "Could not trigger Xcode Command Line Tools installation "
        "automatically. Run xcode-select --install manually, complete the "
        "installer, then rerun this installer."
    )


def ensure_brew() -> None:
    if command_exists("brew"):
        log("Homebrew already installed")
    else:
        log("Installing Homebrew")
        run(
            [
                "/bin/bash",
                "-c",
                "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)",
            ]
        )

    for brew_path in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if is_executable(Path(brew_path)):
            output = run([brew_path, "shellenv"], capture=True).stdout
            for line in output.splitlines():
                match = re.match(r"^export ([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
                if match is None:
                    continue
                name, value = match.groups()
                os.environ[name] = os.path.expandvars(value.strip('"'))


def package_list_installed(output: str, package: str) -> bool:
    return any(
        line.startswith(f"{package} ") or line.startswith(f"{package}@")
        for line in output.splitlines()
    )


def install_brew_package_list(label: str, packages: Sequence[str]) -> None:
    if not packages:
        return

    installed = run(
        ["brew", "list", "--versions", *packages],
        check=False,
        capture=True,
    ).stdout
    missing: list[str] = []

    for package in packages:
        if package_list_installed(installed, package):
            log(f"Already installed: {package}")
        elif run(
            ["brew", "list", "--versions", package],
            check=False,
            capture=True,
        ).returncode == 0:
            log(f"Already installed: {package}")
        else:
            missing.append(package)

    if not missing:
        if label:
            log(f"All requested {label} brew packages are already installed")
        else:
            log("All requested brew packages are already installed")
        return

    if label:
        log(f"Installing missing {label} brew packages: {' '.join(missing)}")
    else:
        log(f"Installing missing brew packages: {' '.join(missing)}")
    run(["brew", "install", *missing])


def install_brew_packages() -> None:
    install_brew_package_list("", BREW_PACKAGES)


def install_brew_k8s_packages() -> None:
    install_brew_package_list("k8s", BREW_K8S_PACKAGES)


def install_brew_casks() -> None:
    installed = f"\n{run(['brew', 'list', '--cask'], check=False, capture=True).stdout}\n"
    missing: list[str] = []

    for cask in BREW_CASKS:
        if f"\n{cask}\n" in installed:
            log(f"Already installed cask: {cask}")
        else:
            missing.append(cask)

    if not missing:
        log("All requested cask apps are already installed")
        return

    log(f"Installing missing brew casks: {' '.join(missing)}")
    run(["brew", "install", "--cask", *missing])


def apt_package_installed(package: str) -> bool:
    result = run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        check=False,
        capture=True,
    )
    return result.stdout == "install ok installed"


def apt_package_available(package: str) -> bool:
    return run(["apt-cache", "show", package], check=False, capture=True).returncode == 0


def sudo_apt_get(*args: str) -> None:
    run(["sudo", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", *args])


def install_apt_packages(
    required_packages: Sequence[str] = APT_PACKAGES,
    optional_packages: Sequence[str] = APT_OPTIONAL_PACKAGES,
) -> None:
    missing: list[str] = []
    unavailable_required: list[str] = []

    log("Updating apt package metadata")
    sudo_apt_get("update")

    for package in required_packages:
        if apt_package_installed(package):
            log(f"Already installed: {package}")
        elif apt_package_available(package):
            missing.append(package)
        else:
            log_err(f"Required apt package is unavailable in configured repositories: {package}")
            unavailable_required.append(package)

    if unavailable_required:
        raise InstallerError(
            f"Cannot continue without required apt packages: {' '.join(unavailable_required)}"
        )

    for package in optional_packages:
        if apt_package_installed(package):
            log(f"Already installed optional apt package: {package}")
        elif apt_package_available(package):
            missing.append(package)
        else:
            log(f"Skipping unavailable optional apt package: {package}")

    if not missing:
        log("All requested apt packages are already installed")
        return

    log(f"Installing missing apt packages: {' '.join(missing)}")
    sudo_apt_get("install", "-y", *missing)


def is_debian_apt_host() -> bool:
    if uname("-s") != "Linux" or not command_exists("apt-get"):
        return False
    os_release = Path("/etc/os-release")
    if not os_release.is_file():
        return False
    return re.search(
        r"^(ID|ID_LIKE)=.*(debian|ubuntu)",
        os_release.read_text(errors="replace"),
        flags=re.MULTILINE | re.IGNORECASE,
    ) is not None


def is_raspbian_host() -> bool:
    os_release = Path("/etc/os-release")
    return os_release.is_file() and re.search(
        r"^ID=raspbian$",
        os_release.read_text(errors="replace"),
        flags=re.MULTILINE,
    ) is not None


def install_uv_tools() -> None:
    ensure_user_local_bin_on_path()
    uv_bin = resolve_uv_bin()
    if uv_bin is None:
        log("uv is not installed; skipping uv tool installation")
        return

    tool_list = run([uv_bin, "tool", "list"], check=False, capture=True).stdout
    any_installed = False
    for tool in UV_TOOL_PACKAGES:
        if re.search(rf"^{re.escape(tool)} v", tool_list, flags=re.MULTILINE):
            any_installed = True
            if state.CURRENT_OPTIONS.upgrade:
                log(f"Upgrading uv tool: {tool}")
                run([uv_bin, "tool", "upgrade", tool])
            else:
                log(f"Already installed uv tool: {tool}")
        else:
            log(f"Installing uv tool: {tool}")
            run([uv_bin, "tool", "install", f"{tool}@latest"])

    if not any_installed and not state.CURRENT_OPTIONS.upgrade:
        log("Installed requested uv tools")
