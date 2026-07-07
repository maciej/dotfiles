from __future__ import annotations

import subprocess

from helpers import ROOT_DIR


def test_make_rejects_unknown_install_target() -> None:
    result = subprocess.run(
        ["make", "-C", str(ROOT_DIR), "-n", "install"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert result.returncode != 0
    assert "Unknown target(s): install" in result.stdout
