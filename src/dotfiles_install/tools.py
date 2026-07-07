from __future__ import annotations

from pathlib import Path

import shutil

from . import state
from .config import (
    BAT_TEMP_MIN_FREE_BYTES,
    GIT_DELTA_TEMP_MIN_FREE_BYTES,
    HELIX_TEMP_MIN_FREE_BYTES,
    KUBECTL_TEMP_MIN_FREE_BYTES,
    KUBIE_TEMP_MIN_FREE_BYTES,
)
from .core import (
    command_exists,
    ensure_user_local_bin_on_path,
    home_dir,
    is_executable,
    log,
    run,
    uname,
)
from .downloads import (
    curl_download,
    curl_head_value,
    curl_text,
    download_size_for_url,
    install_plain_binary_local,
    install_release_binary_local,
    managed_temp_dir,
    require_command,
    resolve_github_release_asset,
)
from .errors import InstallerError
from .package_managers import apt_package_available, is_raspbian_host, sudo_apt_get


def install_kubectl_linux_local() -> None:
    binary_path = home_dir() / ".local/bin/kubectl"
    installed = is_executable(binary_path)
    if installed and not state.CURRENT_OPTIONS.upgrade:
        log("kubectl already installed")
        return

    arch = uname("-m")
    if arch in {"x86_64", "amd64"}:
        kubectl_arch = "amd64"
    elif arch in {"aarch64", "arm64"}:
        kubectl_arch = "arm64"
    else:
        log(f"No official kubectl Linux binary is available for {arch or 'unknown'}; skipping kubectl installation")
        return

    version = curl_text("https://dl.k8s.io/release/stable.txt").strip()
    if not version:
        raise InstallerError("Could not determine latest stable kubectl release")

    download_url = f"https://dl.k8s.io/release/{version}/bin/linux/{kubectl_arch}/kubectl"
    install_plain_binary_local(
        "kubectl",
        "kubectl",
        download_url,
        KUBECTL_TEMP_MIN_FREE_BYTES,
        f"{download_url}.sha256",
        installed=installed,
    )


def install_kubie_linux_local() -> None:
    binary_path = home_dir() / ".local/bin/kubie"
    installed = is_executable(binary_path)
    if installed and not state.CURRENT_OPTIONS.upgrade:
        log("kubie already installed")
        return

    arch = uname("-m")
    if arch in {"x86_64", "amd64"}:
        asset_pattern = "kubie-linux-amd64"
    elif arch in {"aarch64", "arm64"}:
        asset_pattern = "kubie-linux-arm64"
    elif arch in {"armv6l", "armv7l", "armhf"}:
        asset_pattern = "kubie-linux-arm32"
    else:
        log(f"No official kubie Linux binary is available for {arch or 'unknown'}; skipping kubie installation")
        return

    asset_url, _, asset_size_bytes = resolve_github_release_asset(
        "kubie-org/kubie",
        asset_pattern,
    )
    if not asset_url:
        raise InstallerError(
            f"Could not find an official kubie release asset matching {asset_pattern}"
        )

    install_plain_binary_local(
        "kubie",
        "kubie",
        asset_url,
        KUBIE_TEMP_MIN_FREE_BYTES,
        download_size_bytes=asset_size_bytes,
        installed=installed,
    )


def install_bat_local() -> None:
    os_name = uname("-s")
    arch = uname("-m")
    patterns = {
        ("Darwin", "arm64"): "aarch64-apple-darwin.tar.gz",
        ("Darwin", "aarch64"): "aarch64-apple-darwin.tar.gz",
        ("Darwin", "x86_64"): "x86_64-apple-darwin.tar.gz",
        ("Darwin", "amd64"): "x86_64-apple-darwin.tar.gz",
        ("Linux", "aarch64"): "aarch64-unknown-linux-gnu.tar.gz",
        ("Linux", "arm64"): "aarch64-unknown-linux-gnu.tar.gz",
        ("Linux", "x86_64"): "x86_64-unknown-linux-gnu.tar.gz",
        ("Linux", "amd64"): "x86_64-unknown-linux-gnu.tar.gz",
        ("Linux", "armv6l"): "arm-unknown-linux-gnueabihf.tar.gz",
        ("Linux", "armv7l"): "arm-unknown-linux-gnueabihf.tar.gz",
        ("Linux", "armhf"): "arm-unknown-linux-gnueabihf.tar.gz",
        ("Linux", "i386"): "i686-unknown-linux-gnu.tar.gz",
        ("Linux", "i686"): "i686-unknown-linux-gnu.tar.gz",
    }
    asset_pattern = patterns.get((os_name, arch))
    if asset_pattern is None:
        log(
            "No official user-local bat release is available for "
            f"{os_name or 'unknown'}/{arch or 'unknown'}; skipping bat installation"
        )
        return

    install_release_binary_local(
        "bat",
        "sharkdp/bat",
        asset_pattern,
        "bat",
        BAT_TEMP_MIN_FREE_BYTES,
        state.CURRENT_OPTIONS.upgrade,
    )


def install_git_delta_local() -> None:
    os_name = uname("-s")
    arch = uname("-m")
    patterns = {
        ("Darwin", "arm64"): "aarch64-apple-darwin.tar.gz",
        ("Darwin", "aarch64"): "aarch64-apple-darwin.tar.gz",
        ("Linux", "aarch64"): "aarch64-unknown-linux-gnu.tar.gz",
        ("Linux", "arm64"): "aarch64-unknown-linux-gnu.tar.gz",
        ("Linux", "x86_64"): "x86_64-unknown-linux-gnu.tar.gz",
        ("Linux", "amd64"): "x86_64-unknown-linux-gnu.tar.gz",
        ("Linux", "armv6l"): "arm-unknown-linux-gnueabihf.tar.gz",
        ("Linux", "armv7l"): "arm-unknown-linux-gnueabihf.tar.gz",
        ("Linux", "armhf"): "arm-unknown-linux-gnueabihf.tar.gz",
        ("Linux", "i386"): "i686-unknown-linux-gnu.tar.gz",
        ("Linux", "i686"): "i686-unknown-linux-gnu.tar.gz",
    }
    asset_pattern = patterns.get((os_name, arch))
    if asset_pattern is None:
        log(
            "No official user-local git-delta release is available for "
            f"{os_name or 'unknown'}/{arch or 'unknown'}; skipping git-delta installation"
        )
        return

    install_release_binary_local(
        "git-delta",
        "dandavison/delta",
        asset_pattern,
        "delta",
        GIT_DELTA_TEMP_MIN_FREE_BYTES,
        state.CURRENT_OPTIONS.upgrade,
    )


def install_git_delta_linux() -> None:
    apt_status = run(
        ["dpkg-query", "-W", "-f=${Status}", "git-delta"],
        check=False,
        capture=True,
    ).stdout
    if apt_status == "install ok installed" or command_exists("delta"):
        log("git-delta already installed")
        return

    if apt_package_available("git-delta"):
        log("Installing git-delta from apt repositories")
        sudo_apt_get("install", "-y", "git-delta")
        return

    arch = run(["dpkg", "--print-architecture"], check=False, capture=True).stdout.strip()
    deb_arch_by_arch = {
        "amd64": "amd64",
        "arm64": "arm64",
        "armhf": "armhf",
        "i386": "i386",
    }
    deb_arch = deb_arch_by_arch.get(arch)
    if deb_arch is None:
        log(f"No git-delta .deb asset for architecture {arch or 'unknown'}; skipping git-delta installation")
        return

    require_command("curl", "git-delta installer requires curl")
    latest_url = curl_head_value(
        "https://github.com/dandavison/delta/releases/latest",
        "%{url_effective}",
    )
    tag = latest_url.rstrip("/").split("/")[-1]
    if not tag or tag == "latest":
        raise InstallerError("Could not determine latest git-delta release tag")

    version = tag.removeprefix("v")
    download_url = (
        "https://github.com/dandavison/delta/releases/download/"
        f"{tag}/git-delta_{version}_{deb_arch}.deb"
    )
    download_size_bytes = download_size_for_url(download_url)
    required_bytes = max(download_size_bytes or 0, GIT_DELTA_TEMP_MIN_FREE_BYTES)
    with managed_temp_dir(required_bytes, "git-delta download", "git-delta") as temp_dir:
        deb_path = temp_dir / "git-delta.deb"
        curl_download(download_url, deb_path)
        deb_path.chmod(0o644)
        sudo_apt_get("install", "-y", str(deb_path))

    log("Installed git-delta from upstream .deb release")


def install_codex_cli_local() -> None:
    ensure_user_local_bin_on_path()
    codex_bin = home_dir() / ".local/bin/codex"
    installed = is_executable(codex_bin)

    if installed and not state.CURRENT_OPTIONS.upgrade:
        log("Codex CLI already installed")
        return

    if command_exists("curl"):
        if installed:
            log("Upgrading Codex CLI via OpenAI standalone installer")
        else:
            log("Installing Codex CLI via OpenAI standalone installer")
        installer = run(
            ["curl", "-fsSL", "https://chatgpt.com/codex/install.sh"],
            capture=True,
        ).stdout
    elif command_exists("wget"):
        if installed:
            log("Upgrading Codex CLI via OpenAI standalone installer")
        else:
            log("Installing Codex CLI via OpenAI standalone installer")
        installer = run(
            ["wget", "-qO-", "https://chatgpt.com/codex/install.sh"],
            capture=True,
        ).stdout
    else:
        raise InstallerError("Codex CLI installer requires curl or wget")

    run(
        ["sh"],
        input_text=installer,
        env={
            "CODEX_INSTALL_DIR": str(home_dir() / ".local/bin"),
            "CODEX_HOME": str(home_dir() / ".codex"),
            "CODEX_NON_INTERACTIVE": "1",
        },
    )
    ensure_user_local_bin_on_path()


def install_helix_linux_via_snap() -> None:
    helix_bin = home_dir() / ".local/bin/hx"
    installed = False
    if command_exists("snap"):
        installed = run(["snap", "list", "helix"], check=False, capture=True).returncode == 0

    if not command_exists("snap"):
        log("Installing snapd from apt repositories for Helix armhf support")
        sudo_apt_get("install", "-y", "snapd")

    if command_exists("systemctl"):
        run(["sudo", "systemctl", "enable", "--now", "snapd.socket"])

    if not Path("/snap").exists() and Path("/var/lib/snapd/snap").is_dir():
        run(["sudo", "ln", "-s", "/var/lib/snapd/snap", "/snap"])

    if run(["snap", "list", "snapd"], check=False, capture=True).returncode != 0:
        log("Installing snapd snap per Snapcraft Raspbian instructions")
        run(["sudo", "snap", "install", "snapd"])

    if installed:
        if state.CURRENT_OPTIONS.upgrade:
            log("Refreshing Helix from Snapcraft")
            run(["sudo", "snap", "refresh", "helix"])
        else:
            log("helix already installed")
    else:
        log("Installing Helix from Snapcraft")
        run(["sudo", "snap", "install", "helix", "--classic"])

    helix_bin.parent.mkdir(parents=True, exist_ok=True)
    run(["ln", "-sfn", "/snap/bin/hx", helix_bin])
    log(f"Linked Helix snap launcher into {helix_bin}")


def resolve_helix_release_asset(asset_pattern: str) -> tuple[str, str, int | None]:
    asset_url, asset_name, asset_size = resolve_github_release_asset(
        "helix-editor/helix",
        asset_pattern,
    )
    if asset_url:
        return asset_url, asset_name, asset_size

    latest_url = run(
        [
            "curl",
            "-fsSLI",
            "-o",
            "/dev/null",
            "-w",
            "%{url_effective}",
            "https://github.com/helix-editor/helix/releases/latest",
        ],
        check=False,
        capture=True,
    ).stdout.strip()
    tag = latest_url.rstrip("/").split("/")[-1]
    if tag and tag != "latest":
        asset_name = f"helix-{tag}-{asset_pattern}"
        asset_url = (
            "https://github.com/helix-editor/helix/releases/download/"
            f"{tag}/{asset_name}"
        )
        return asset_url, asset_name, None

    return "", "", None


def install_helix_from_release_asset(asset_pattern: str, local_only: bool = False) -> None:
    helix_bin = home_dir() / ".local/bin/hx"
    installed = is_executable(helix_bin)
    if not local_only and command_exists("hx"):
        installed = True

    if installed and not state.CURRENT_OPTIONS.upgrade:
        log("helix already installed")
        return

    require_command("curl", "Helix installer requires curl")
    require_command("tar", "Helix installer requires tar")

    asset_url, asset_name, asset_size_bytes = resolve_helix_release_asset(asset_pattern)
    if not asset_url:
        raise InstallerError(
            f"Could not find an official Helix release asset matching {asset_pattern}"
        )

    required_bytes = max(asset_size_bytes or 0, HELIX_TEMP_MIN_FREE_BYTES)
    purpose = f"Helix archive download and extraction ({asset_name})"
    with managed_temp_dir(required_bytes, purpose, "helix") as temp_dir:
        tarball = temp_dir / "helix.tar.xz"
        curl_download(asset_url, tarball)
        run(["tar", "-xJf", tarball, "-C", temp_dir])

        extracted_dir = next(
            (
                candidate
                for candidate in temp_dir.iterdir()
                if candidate.is_dir() and candidate.name.startswith("helix-")
            ),
            None,
        )
        if (
            extracted_dir is None
            or not is_executable(extracted_dir / "hx")
            or not (extracted_dir / "runtime").is_dir()
        ):
            raise InstallerError(
                "Helix release archive did not contain the expected files"
            )

        helix_bin.parent.mkdir(parents=True, exist_ok=True)
        (home_dir() / ".config/helix").mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted_dir / "hx", helix_bin)
        helix_bin.chmod(0o755)

        runtime_path = home_dir() / ".config/helix/runtime"
        shutil.rmtree(runtime_path, ignore_errors=True)
        shutil.copytree(extracted_dir / "runtime", runtime_path)

    if installed:
        log("Upgraded Helix from official release asset")
    else:
        log("Installed Helix from official release asset")


def install_helix_linux() -> None:
    arch = uname("-m")
    if arch in {"aarch64", "arm64"}:
        asset_pattern = "aarch64-linux.tar.xz"
    elif arch in {"x86_64", "amd64"}:
        asset_pattern = "x86_64-linux.tar.xz"
    elif arch in {"armv6l", "armv7l", "armhf"}:
        if is_raspbian_host():
            install_helix_linux_via_snap()
        else:
            log(f"No official Helix Linux release is available for {arch}; skipping Helix installation")
        return
    else:
        log(f"Unsupported Helix Linux architecture ({arch or 'unknown'}); skipping Helix installation")
        return

    install_helix_from_release_asset(asset_pattern)


def install_helix_local() -> None:
    os_name = uname("-s")
    arch = uname("-m")
    patterns = {
        ("Darwin", "arm64"): "aarch64-macos.tar.xz",
        ("Darwin", "aarch64"): "aarch64-macos.tar.xz",
        ("Darwin", "x86_64"): "x86_64-macos.tar.xz",
        ("Darwin", "amd64"): "x86_64-macos.tar.xz",
        ("Linux", "aarch64"): "aarch64-linux.tar.xz",
        ("Linux", "arm64"): "aarch64-linux.tar.xz",
        ("Linux", "x86_64"): "x86_64-linux.tar.xz",
        ("Linux", "amd64"): "x86_64-linux.tar.xz",
    }
    asset_pattern = patterns.get((os_name, arch))
    if asset_pattern is None:
        log(
            "No official user-local Helix release is available for "
            f"{os_name or 'unknown'}/{arch or 'unknown'}; skipping Helix installation"
        )
        return

    install_helix_from_release_asset(asset_pattern, local_only=True)
