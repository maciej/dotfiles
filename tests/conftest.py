from __future__ import annotations

import os
from pathlib import Path

import pytest

from helpers import ROOT_DIR

import dotfiles_install as installer
from dotfiles_install import state


@pytest.fixture(autouse=True)
def installer_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv(
        "SSH_CONFIG_INCLUDE_PATTERN",
        str(tmp_path / ".ssh/config.d/*.conf"),
    )
    state.DOTFILES_DIR = ROOT_DIR
    state.CURRENT_OPTIONS = installer.Options()
    yield
    state.DOTFILES_DIR = ROOT_DIR
    state.CURRENT_OPTIONS = installer.Options()


@pytest.fixture
def temp_home(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def fake_bin(temp_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = temp_home / "fake-bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return bin_dir
