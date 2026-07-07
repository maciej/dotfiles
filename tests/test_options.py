from __future__ import annotations

import os
from pathlib import Path

import pytest

import dotfiles_install as installer

from helpers import assert_file_equals


def test_local_install_marker_uses_xdg_config_home(
    temp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(temp_home / "xdg-config"))

    assert installer.local_install_marker_path() == (
        temp_home / "xdg-config/dotfiles/install-mode"
    )


def test_local_install_marker_defaults_to_home_config(temp_home: Path) -> None:
    os.environ.pop("XDG_CONFIG_HOME", None)

    assert installer.local_install_marker_path() == (
        temp_home / ".config/dotfiles/install-mode"
    )


def test_local_install_marker_enables_local_default() -> None:
    marker = installer.local_install_marker_path()
    marker.parent.mkdir(parents=True)
    marker.write_text("local\n")
    options = installer.parse_args([])

    installer.apply_local_install_default(options)

    assert options.local_install


def test_explicit_local_writes_marker() -> None:
    options = installer.parse_args(["--local"])

    installer.apply_local_install_default(options)
    installer.update_local_install_default_marker(options)

    assert options.local_install
    assert_file_equals(installer.local_install_marker_path(), "local")


def test_no_local_clears_marker() -> None:
    marker = installer.local_install_marker_path()
    marker.parent.mkdir(parents=True)
    marker.write_text("local\n")
    options = installer.parse_args(["--no-local"])

    installer.apply_local_install_default(options)
    installer.update_local_install_default_marker(options)

    assert not options.local_install
    assert not marker.exists()


def test_with_group_accepts_repeated_and_comma_separated_values() -> None:
    options = installer.parse_args(["--with", "k8s,k8s", "--with=k8s"])

    assert options.with_groups == ["k8s"]


def test_with_group_rejects_unknown_group() -> None:
    with pytest.raises(
        installer.InstallerUsageError,
        match="Unknown optional tool group: nope",
    ):
        installer.parse_args(["--with", "nope"])


def test_with_group_requires_value() -> None:
    with pytest.raises(
        installer.InstallerUsageError,
        match="--with requires an optional tool group.",
    ):
        installer.parse_args(["--with"])


def test_local_with_group_is_invalid() -> None:
    options = installer.parse_args(["--local", "--with", "k8s"])

    with pytest.raises(
        installer.InstallerError,
        match="--with installs optional system tool groups",
    ):
        installer.validate_install_mode_options(options)


def test_with_group_ignores_local_install_default_for_this_run() -> None:
    marker = installer.local_install_marker_path()
    marker.parent.mkdir(parents=True)
    marker.write_text("local\n")
    options = installer.parse_args(["--with", "k8s"])

    installer.validate_install_mode_options(options)
    installer.apply_local_install_default(options)
    installer.update_local_install_default_marker(options)

    assert not options.local_install
    assert_file_equals(marker, "local")
