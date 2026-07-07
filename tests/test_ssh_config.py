from __future__ import annotations

import os
import subprocess
from pathlib import Path

import dotfiles_install as installer

from helpers import assert_file_equals, require_ssh


def test_creates_missing_config(temp_home: Path) -> None:
    old_umask = os.umask(0)
    os.umask(old_umask)

    installer.ensure_ssh_config_fragment_directory()
    installer.ensure_ssh_config_include()

    assert_file_equals(
        temp_home / ".ssh/config",
        f"Include {os.environ['SSH_CONFIG_INCLUDE_PATTERN']}",
    )
    current_umask = os.umask(old_umask)
    os.umask(current_umask)
    assert current_umask == old_umask


def test_inserts_before_first_host(temp_home: Path) -> None:
    installer.ensure_ssh_config_fragment_directory()
    config = temp_home / ".ssh/config"
    config.write_text(
        "CanonicalizeHostname yes\n\n"
        "Host example\n"
        "  User local\n"
    )

    installer.ensure_ssh_config_include()

    assert_file_equals(
        config,
        "CanonicalizeHostname yes\n\n"
        f"Include {os.environ['SSH_CONFIG_INCLUDE_PATTERN']}\n"
        "Host example\n"
        "  User local",
    )


def test_appends_without_host_blocks(temp_home: Path) -> None:
    installer.ensure_ssh_config_fragment_directory()
    config = temp_home / ".ssh/config"
    config.write_text("CanonicalizeHostname yes\nHashKnownHosts yes\n")

    installer.ensure_ssh_config_include()

    assert_file_equals(
        config,
        "CanonicalizeHostname yes\n"
        "HashKnownHosts yes\n"
        f"Include {os.environ['SSH_CONFIG_INCLUDE_PATTERN']}",
    )


def test_is_idempotent(temp_home: Path) -> None:
    installer.ensure_ssh_config_fragment_directory()
    config = temp_home / ".ssh/config"
    config.write_text(f"Include {os.environ['SSH_CONFIG_INCLUDE_PATTERN']}\n")

    installer.ensure_ssh_config_include()
    installer.ensure_ssh_config_include()

    assert_file_equals(
        config,
        f"Include {os.environ['SSH_CONFIG_INCLUDE_PATTERN']}",
    )


def test_ssh_reads_included_fragment(temp_home: Path) -> None:
    require_ssh()

    installer.ensure_ssh_config_fragment_directory()
    (temp_home / ".ssh/config.d/example.conf").write_text(
        "Host git.example.test\n"
        "  User git\n"
        "  Port 2222\n"
    )
    (temp_home / ".ssh/config").write_text(
        "Host *\n"
        "  User fallback\n"
    )

    installer.ensure_ssh_config_include()

    rendered = subprocess.run(
        [
            "ssh",
            "-F",
            str(temp_home / ".ssh/config"),
            "-G",
            "git.example.test",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout
    assert "user git\n" in rendered
    assert "port 2222\n" in rendered
