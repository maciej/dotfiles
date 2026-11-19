from __future__ import annotations

import hashlib
import shutil
import tarfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from helpers import assert_executable, assert_file_equals, make_executable

import dotfiles_install as installer
from dotfiles_install import cli, state, tools
from dotfiles_install.errors import InstallerError


def test_codex_local_installer_uses_home_scoped_env(
    fake_bin: Path,
    temp_home: Path,
) -> None:
    capture = temp_home / "codex-env"
    make_executable(
        fake_bin / "curl",
        """\
        #!/usr/bin/env bash
        printf '# fake Codex installer\\n'
        """,
    )
    make_executable(
        fake_bin / "sh",
        f"""\
        #!/usr/bin/env bash
        while IFS= read -r _line; do
          :
        done
        {{
          printf 'CODEX_INSTALL_DIR=%s\\n' "${{CODEX_INSTALL_DIR:-}}"
          printf 'CODEX_HOME=%s\\n' "${{CODEX_HOME:-}}"
          printf 'CODEX_NON_INTERACTIVE=%s\\n' "${{CODEX_NON_INTERACTIVE:-}}"
        }} >"{capture}"
        """,
    )

    installer.install_codex_cli_local()

    assert_file_equals(
        capture,
        f"CODEX_INSTALL_DIR={temp_home}/.local/bin\n"
        f"CODEX_HOME={temp_home}/.codex\n"
        "CODEX_NON_INTERACTIVE=1",
    )


@pytest.mark.parametrize(("arch", "asset_arch"), [("arm64", "aarch64"), ("amd64", "x86_64")])
def test_worktrunk_installer_uses_pinned_archive_and_keeps_existing_on_mismatch(
    temp_home: Path, monkeypatch: pytest.MonkeyPatch, arch: str, asset_arch: str,
) -> None:
    monkeypatch.setenv("PATH", str(temp_home / ".local/bin"))
    monkeypatch.delenv("CARGO_HOME", raising=False)
    monkeypatch.delenv("CARGO_INSTALL_ROOT", raising=False)
    release = f"worktrunk-{asset_arch}-unknown-linux-musl"
    archive_path = temp_home / f"{release}.tar.xz"
    fixture = temp_home / "fixture-wt"
    make_executable(fixture, "pinned binary")
    with tarfile.open(archive_path, "w:xz") as archive:
        archive.add(fixture, arcname=f"{release}/wt")
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    monkeypatch.setattr(tools, "uname", lambda _: arch)
    monkeypatch.setattr(tools, "WORKTRUNK_LINUX_SHA256", {asset_arch: checksum})

    def download(url: str, destination: Path) -> None:
        assert url == (
            "https://github.com/max-sixty/worktrunk/releases/download/"
            f"v{tools.WORKTRUNK_VERSION}/{release}.tar.xz"
        )
        shutil.copyfile(archive_path, destination)

    download_mock = Mock(side_effect=download)
    monkeypatch.setattr(tools, "curl_download", download_mock)

    tools.install_worktrunk_linux_local()
    binary = temp_home / ".local/bin/wt"
    assert_executable(binary)
    assert binary.read_bytes() == fixture.read_bytes()

    tools.install_worktrunk_linux_local()
    assert download_mock.call_count == 1

    monkeypatch.setattr(state.CURRENT_OPTIONS, "upgrade", True)
    archive_path.write_bytes(b"corrupt archive")
    with pytest.raises(InstallerError, match="checksum verification failed"):
        tools.install_worktrunk_linux_local()
    assert binary.read_bytes() == fixture.read_bytes()


def test_worktrunk_installer_skips_cargo_even_when_upgrading(
    temp_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", str(temp_home / ".local/bin"))
    monkeypatch.delenv("CARGO_HOME", raising=False)
    cargo_root = temp_home / "custom-cargo"
    (cargo_root / "bin").mkdir(parents=True)
    make_executable(cargo_root / "bin/wt", "cargo binary")
    (cargo_root / ".crates.toml").write_text('[v1]\n"worktrunk 0.81.0 (registry+https://example.test)" = ["wt"]\n')
    monkeypatch.setenv("CARGO_INSTALL_ROOT", str(cargo_root))
    monkeypatch.setattr(state.CURRENT_OPTIONS, "upgrade", True)
    download = Mock()
    monkeypatch.setattr(tools, "curl_download", download)

    tools.install_worktrunk_linux_local()

    download.assert_not_called()
    assert not (temp_home / ".local/bin/wt").exists()


@pytest.mark.parametrize(("local", "apt_host"), [(True, False), (False, True), (False, False)])
def test_linux_install_modes_include_worktrunk(
    monkeypatch: pytest.MonkeyPatch, local: bool, apt_host: bool,
) -> None:
    monkeypatch.setattr(cli, "uname", lambda _: "Linux")
    monkeypatch.setattr(cli, "is_debian_apt_host", lambda: apt_host)
    for name in (
        "ensure_user_local_bin_on_path", "install_apt_packages", "install_bat_local",
        "install_git_delta_local", "install_git_delta_linux",
        "install_helix_local", "install_helix_linux", "install_codex_cli_local", "install_uv_tools",
        "install_ghostty_terminfo", "finish_stow_and_shell_setup",
    ):
        monkeypatch.setattr(cli, name, Mock())
    worktrunk = Mock()
    monkeypatch.setattr(cli, "install_worktrunk_linux_local", worktrunk)

    cli.main_install(installer.Options(local_install=local))

    worktrunk.assert_called_once_with()


@pytest.mark.parametrize(
    ("os_name", "arch"),
    [
        ("Linux", "x86_64"),
        ("Darwin", "arm64"),
    ],
)
def test_local_release_installers_install_bat_and_delta(
    fake_bin: Path,
    temp_home: Path,
    os_name: str,
    arch: str,
) -> None:
    make_executable(
        fake_bin / "curl",
        """\
        #!/usr/bin/env bash
        output_file=""
        url=""
        while (( $# > 0 )); do
          case "$1" in
            -o)
              output_file="$2"
              shift 2
              ;;
            -*)
              shift
              ;;
            *)
              url="$1"
              shift
              ;;
          esac
        done

        case "${url}" in
          https://api.github.com/repos/sharkdp/bat/releases/latest)
            cat <<'JSON'
        {"assets":[{"name":"bat-v0.0.0-x86_64-unknown-linux-gnu.tar.gz","browser_download_url":"https://example.test/bat-v0.0.0-x86_64-unknown-linux-gnu.tar.gz","size":1024},{"name":"bat-v0.0.0-aarch64-apple-darwin.tar.gz","browser_download_url":"https://example.test/bat-v0.0.0-aarch64-apple-darwin.tar.gz","size":1024}]}
        JSON
            ;;
          https://api.github.com/repos/dandavison/delta/releases/latest)
            cat <<'JSON'
        {"assets":[{"name":"delta-0.0.0-x86_64-unknown-linux-gnu.tar.gz","browser_download_url":"https://example.test/delta-0.0.0-x86_64-unknown-linux-gnu.tar.gz","size":1024},{"name":"delta-0.0.0-aarch64-apple-darwin.tar.gz","browser_download_url":"https://example.test/delta-0.0.0-aarch64-apple-darwin.tar.gz","size":1024}]}
        JSON
            ;;
          https://example.test/*)
            printf 'fake archive' >"${output_file:?}"
            ;;
          *)
            printf 'unexpected curl URL: %s\\n' "${url}" >&2
            exit 1
            ;;
        esac
        """,
    )
    make_executable(
        fake_bin / "tar",
        """\
        #!/usr/bin/env bash
        archive=""
        dest=""
        while (( $# > 0 )); do
          case "$1" in
            -C)
              dest="$2"
              shift 2
              ;;
            -*)
              shift
              ;;
            *)
              archive="$1"
              shift
              ;;
          esac
        done

        case "${archive}" in
          *bat*)
            mkdir -p "${dest:?}/bat-release"
            printf 'bat binary' >"${dest}/bat-release/bat"
            chmod 700 "${dest}/bat-release/bat"
            ;;
          *delta*)
            mkdir -p "${dest:?}/delta-release"
            printf 'delta binary' >"${dest}/delta-release/delta"
            chmod 700 "${dest}/delta-release/delta"
            ;;
          *)
            printf 'unexpected archive: %s\\n' "${archive}" >&2
            exit 1
            ;;
        esac
        """,
    )
    make_executable(
        fake_bin / "uname",
        f"""\
        #!/usr/bin/env bash
        case "${1:-}" in
          -s)
            printf '{os_name}\\n'
            ;;
          -m)
            printf '{arch}\\n'
            ;;
          *)
            printf '{os_name}\\n'
            ;;
        esac
        """,
    )

    installer.install_bat_local()
    installer.install_git_delta_local()

    bat = temp_home / ".local/bin/bat"
    delta = temp_home / ".local/bin/delta"
    assert_executable(bat)
    assert_executable(delta)
    assert_file_equals(bat, "bat binary")
    assert_file_equals(delta, "delta binary")


def test_k8s_linux_local_installers_install_binaries(
    fake_bin: Path,
    temp_home: Path,
) -> None:
    kubectl_hash = hashlib.sha256(b"kubectl binary").hexdigest()
    make_executable(
        fake_bin / "curl",
        f"""\
        #!/usr/bin/env bash
        output_file=""
        url=""
        write_out=""
        while (( $# > 0 )); do
          case "$1" in
            -o)
              output_file="$2"
              shift 2
              ;;
            -w)
              write_out="$2"
              shift 2
              ;;
            -*)
              shift
              ;;
            *)
              url="$1"
              shift
              ;;
          esac
        done

        if [[ -n "${{write_out}}" ]]; then
          printf '4096'
          exit 0
        fi

        case "${{url}}" in
          https://dl.k8s.io/release/stable.txt)
            printf 'v1.36.2\\n'
            ;;
          https://dl.k8s.io/release/v1.36.2/bin/linux/amd64/kubectl)
            printf 'kubectl binary' >"${{output_file:?}}"
            ;;
          https://dl.k8s.io/release/v1.36.2/bin/linux/amd64/kubectl.sha256)
            printf '{kubectl_hash}' >"${{output_file:?}}"
            ;;
          https://api.github.com/repos/kubie-org/kubie/releases/latest)
            printf '{{"assets":[{{"name":"kubie-linux-amd64","browser_download_url":"https://example.test/kubie-linux-amd64","size":4096}}]}}'
            ;;
          https://example.test/kubie-linux-amd64)
            printf 'kubie binary' >"${{output_file:?}}"
            ;;
          *)
            printf 'unexpected curl URL: %s\\n' "${{url}}" >&2
            exit 1
            ;;
        esac
        """,
    )
    make_executable(
        fake_bin / "uname",
        """\
        #!/usr/bin/env bash
        case "${1:-}" in
          -s)
            printf 'Linux\\n'
            ;;
          -m)
            printf 'x86_64\\n'
            ;;
          *)
            printf 'Linux\\n'
            ;;
        esac
        """,
    )

    installer.install_kubectl_linux_local()
    installer.install_kubie_linux_local()

    kubectl = temp_home / ".local/bin/kubectl"
    kubie = temp_home / ".local/bin/kubie"
    assert_executable(kubectl)
    assert_executable(kubie)
    assert_file_equals(kubectl, "kubectl binary")
    assert_file_equals(kubie, "kubie binary")
