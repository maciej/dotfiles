from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from helpers import ROOT_DIR, assert_file_equals, make_executable


def test_install_sh_delegates_to_uv_script(temp_home: Path) -> None:
    uv_log = temp_home / "uv.log"
    local_bin = temp_home / ".local/bin"
    local_bin.mkdir(parents=True)
    make_executable(
        local_bin / "uv",
        f"""\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >"{uv_log}"
        """,
    )

    result = subprocess.run(
        ["bash", str(ROOT_DIR / "install.sh"), "--local"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert_file_equals(
        uv_log,
        f"run --script {ROOT_DIR / 'src/dotfiles_install/__main__.py'} --local",
    )


@pytest.mark.parametrize("saved_local", [False, True])
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ([], None),
        (["--local"], "local"),
        (["--system"], "system"),
        (["--no-local"], "system"),
        (["--with", "k8s"], "system"),
        (["--upgrade"], None),
    ],
)
def test_show_mode_is_read_only(
    temp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    saved_local: bool,
    args: list[str],
    expected: str | None,
) -> None:
    config_home = temp_home / "custom-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    marker = config_home / "dotfiles/install-mode"
    if saved_local:
        marker.parent.mkdir(parents=True)
        marker.write_text("local\n")
    before = sorted(temp_home.rglob("*"))

    result = subprocess.run(
        ["bash", str(ROOT_DIR / "install.sh"), "--show-mode", *args],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{expected or ('local' if saved_local else 'system')}\n"
    assert result.stderr == ""
    assert sorted(temp_home.rglob("*")) == before
    if saved_local:
        assert marker.read_text() == "local\n"


def test_show_mode_rejects_invalid_options(temp_home: Path) -> None:
    result = subprocess.run(
        ["bash", str(ROOT_DIR / "install.sh"), "--show-mode", "--local", "--with", "k8s"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cannot be combined with --local" in result.stderr
    assert not (temp_home / ".config").exists()
