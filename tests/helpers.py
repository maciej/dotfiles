from __future__ import annotations

import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))


def assert_file_equals(path: Path, expected: str) -> None:
    assert path.read_text().rstrip("\n") == expected


def make_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip())
    path.chmod(0o755)


def assert_executable(path: Path) -> None:
    assert path.is_file()
    assert os.access(path, os.X_OK)


def require_ssh() -> None:
    if shutil.which("ssh") is None:
        pytest.skip("ssh is unavailable")
