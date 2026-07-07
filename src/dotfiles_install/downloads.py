from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .config import MIB
from .core import ensure_user_local_bin_on_path, home_dir, is_executable, log, log_err, run
from .errors import InstallerError


def describe_bytes_in_mib(bytes_count: int) -> str:
    return f"{(bytes_count + MIB - 1) // MIB} MiB"


def available_bytes_for_path(path: Path) -> int:
    return shutil.disk_usage(path).free


def resolve_temp_root(required_bytes: int, purpose: str) -> Path:
    explicit_tmpdir = "TMPDIR" in os.environ and bool(os.environ["TMPDIR"])
    primary_root = Path(os.environ["TMPDIR"]) if explicit_tmpdir else Path("/tmp")
    primary_root.mkdir(parents=True, exist_ok=True)

    primary_available = available_bytes_for_path(primary_root)
    if primary_available >= required_bytes:
        return primary_root

    if explicit_tmpdir:
        raise InstallerError(
            f"TMPDIR ({primary_root}) has only "
            f"{describe_bytes_in_mib(primary_available)} free, but {purpose} "
            f"requires at least {describe_bytes_in_mib(required_bytes)}"
        )

    fallback_root = home_dir() / ".cache/tmp"
    fallback_root.mkdir(parents=True, exist_ok=True)
    fallback_available = available_bytes_for_path(fallback_root)
    if fallback_available < required_bytes:
        raise InstallerError(
            "Default temporary directory (/tmp) has insufficient space and "
            f"fallback {fallback_root} has only "
            f"{describe_bytes_in_mib(fallback_available)} free, but {purpose} "
            f"requires at least {describe_bytes_in_mib(required_bytes)}"
        )

    log_err(
        f"Using fallback temporary directory root {fallback_root} because "
        f"/tmp has insufficient free space for {purpose}"
    )
    return fallback_root


@contextmanager
def managed_temp_dir(required_bytes: int, purpose: str, prefix: str) -> Iterable[Path]:
    temp_root = resolve_temp_root(required_bytes, purpose)
    temp_dir = Path(tempfile.mkdtemp(prefix=f"{prefix}.", dir=temp_root))
    temp_dir.chmod(0o755)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def require_command(command: str, message: str) -> None:
    if shutil.which(command) is None:
        raise InstallerError(message)


def curl_text(url: str) -> str:
    require_command("curl", "curl is required for this installer step")
    return run(["curl", "-fsSL", url], capture=True).stdout


def curl_download(url: str, destination: Path) -> None:
    require_command("curl", "curl is required for this installer step")
    run(["curl", "-fsSL", url, "-o", destination])


def curl_head_value(url: str, write_out: str) -> str:
    require_command("curl", "curl is required for this installer step")
    return run(
        ["curl", "-fsSLI", "-o", "/dev/null", "-w", write_out, url],
        capture=True,
    ).stdout.strip()


def download_size_for_url(url: str) -> int | None:
    output = run(
        ["curl", "-fsSLI", "-o", "/dev/null", "-w", "%{content_length_download}", url],
        check=False,
        capture=True,
    ).stdout.strip()
    if output.isdigit() and int(output) > 0:
        return int(output)
    return None


def resolve_github_release_asset(repo: str, asset_pattern: str) -> tuple[str, str, int | None]:
    release_json = curl_text(f"https://api.github.com/repos/{repo}/releases/latest")
    release = json.loads(release_json)

    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        if name.endswith(asset_pattern):
            url = str(asset.get("browser_download_url", ""))
            size = asset.get("size")
            return url, name, int(size) if isinstance(size, int) and size > 0 else None

    return "", "", None


def install_release_binary_local(
    tool_name: str,
    repo: str,
    asset_pattern: str,
    binary_name: str,
    min_free_bytes: int,
    upgrade: bool,
) -> None:
    ensure_user_local_bin_on_path()
    binary_path = home_dir() / ".local/bin" / binary_name
    installed = is_executable(binary_path)

    if installed and not upgrade:
        log(f"{tool_name} already installed")
        return

    require_command("curl", f"{tool_name} installer requires curl")
    require_command("tar", f"{tool_name} installer requires tar")

    asset_url, asset_name, asset_size_bytes = resolve_github_release_asset(
        repo,
        asset_pattern,
    )
    if not asset_url:
        raise InstallerError(
            f"Could not find an official {tool_name} release asset matching "
            f"{asset_pattern}"
        )

    required_bytes = max(asset_size_bytes or 0, min_free_bytes)
    purpose = f"{tool_name} archive download and extraction ({asset_name})"
    with managed_temp_dir(required_bytes, purpose, binary_name) as temp_dir:
        tarball = temp_dir / asset_name
        curl_download(asset_url, tarball)
        run(["tar", "-xzf", tarball, "-C", temp_dir])

        extracted_binary = next(
            (
                candidate
                for candidate in temp_dir.rglob(binary_name)
                if is_executable(candidate)
            ),
            None,
        )
        if extracted_binary is None:
            raise InstallerError(
                f"{tool_name} release archive did not contain an executable "
                f"{binary_name} binary"
            )

        binary_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted_binary, binary_path)
        binary_path.chmod(0o755)

    if installed:
        log(f"Upgraded {tool_name} from official release asset")
    else:
        log(f"Installed {tool_name} from official release asset")


def install_plain_binary_local(
    tool_name: str,
    binary_name: str,
    download_url: str,
    min_free_bytes: int,
    checksum_url: str = "",
    download_size_bytes: int | None = None,
    installed: bool = False,
) -> None:
    ensure_user_local_bin_on_path()
    binary_path = home_dir() / ".local/bin" / binary_name
    require_command("curl", f"{tool_name} installer requires curl")

    size = download_size_bytes or download_size_for_url(download_url)
    required_bytes = max(size or 0, min_free_bytes)

    with managed_temp_dir(required_bytes, f"{tool_name} binary download", binary_name) as temp_dir:
        downloaded_binary = temp_dir / binary_name
        curl_download(download_url, downloaded_binary)

        if checksum_url:
            checksum_file = temp_dir / f"{binary_name}.sha256"
            curl_download(checksum_url, checksum_file)
            checksum = checksum_file.read_text().strip().split()[0]
            if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
                raise InstallerError(
                    f"{tool_name} checksum file did not contain a SHA-256 digest"
                )
            digest = hashlib.sha256(downloaded_binary.read_bytes()).hexdigest()
            if digest.lower() != checksum.lower():
                raise InstallerError(f"{tool_name} checksum verification failed")

        binary_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(downloaded_binary, binary_path)
        binary_path.chmod(0o755)

    if installed:
        log(f"Upgraded {tool_name} from official binary release")
    else:
        log(f"Installed {tool_name} from official binary release")
