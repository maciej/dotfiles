from __future__ import annotations

import os
from pathlib import Path

import pytest

import dotfiles_install as installer

from helpers import assert_file_equals, make_executable


@pytest.fixture
def fake_apt(fake_bin: Path, temp_home: Path) -> Path:
    log_file = temp_home / "apt.log"
    make_executable(
        fake_bin / "sudo",
        """\
        #!/usr/bin/env bash
        exec "$@"
        """,
    )
    make_executable(
        fake_bin / "apt-get",
        """\
        #!/usr/bin/env bash
        printf 'apt-get %s\\n' "$*" >>"${APT_TEST_LOG:?}"
        """,
    )
    make_executable(
        fake_bin / "apt-cache",
        """\
        #!/usr/bin/env bash
        if [[ "${1:-}" != "show" ]]; then
          printf 'unexpected apt-cache command: %s\\n' "$*" >&2
          exit 1
        fi

        case " ${APT_TEST_AVAILABLE:-} " in
          *" ${2:-} "*)
            printf 'Package: %s\\n' "$2"
            ;;
          *)
            exit 100
            ;;
        esac
        """,
    )
    make_executable(
        fake_bin / "dpkg-query",
        """\
        #!/usr/bin/env bash
        pkg="${@: -1}"
        case " ${APT_TEST_INSTALLED:-} " in
          *" ${pkg} "*)
            printf 'install ok installed'
            ;;
          *)
            exit 1
            ;;
        esac
        """,
    )
    os.environ["APT_TEST_LOG"] = str(log_file)
    return log_file


def test_apt_skips_unavailable_optional_packages(fake_apt: Path) -> None:
    os.environ["APT_TEST_AVAILABLE"] = "curl git"
    os.environ["APT_TEST_INSTALLED"] = ""

    installer.install_apt_packages(["curl", "git"], ["lazygit"])

    assert_file_equals(
        fake_apt,
        "apt-get update\n"
        "apt-get install -y curl git",
    )


def test_apt_fails_when_required_package_is_unavailable(fake_apt: Path) -> None:
    os.environ["APT_TEST_AVAILABLE"] = "curl"
    os.environ["APT_TEST_INSTALLED"] = ""

    with pytest.raises(
        installer.InstallerError,
        match="Cannot continue without required apt packages: missing-required",
    ):
        installer.install_apt_packages(["curl", "missing-required"], ["lazygit"])

    assert_file_equals(fake_apt, "apt-get update")
