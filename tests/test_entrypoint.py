from __future__ import annotations

import subprocess
from pathlib import Path

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert_file_equals(
        uv_log,
        f"run --script {ROOT_DIR / 'src/dotfiles_install/__main__.py'} --local",
    )
