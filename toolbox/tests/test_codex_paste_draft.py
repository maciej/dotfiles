from __future__ import annotations

import fcntl
import os
import pty
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time
from contextlib import suppress
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "src/codex_paste_draft.py"
DRAFT = (
    "This worktree is at the head of https://github.com/example-org/example-project/pull/42."
    "\n\nExplain and review the PR."
)


def test_draft_is_pasted_only_after_idle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex = tmp_path / "codex"
    codex.write_text(
        f"#!{sys.executable}\n"
        """\
import os
import select
import sys
import time
import tty

assert len(sys.argv) == 1
assert tuple(os.get_terminal_size()) == (92, 27)
tty.setraw(0)
os.write(1, b"\\x1b]7501;state=blocked:app=codex\\x1b\\\\")
assert not select.select([0], [], [], 0.1)[0]
os.write(1, b"\\x1b]7501;state=")
time.sleep(0.05)
os.write(1, b"idle:app=codex\\x1b\\\\")
received = b""
while not received.endswith(b"\\x1b[201~"):
    received += os.read(0, 4096)
os.write(2, received)
assert not select.select([0], [], [], 0.1)[0]
sys.exit(7)
"""
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    master, terminal = pty.openpty()
    try:
        fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", 27, 92, 0, 0))
        original_mode = termios.tcgetattr(terminal)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), DRAFT],
            check=False,
            stdin=terminal,
            stdout=terminal,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        assert termios.tcgetattr(terminal) == original_mode
        output = os.read(master, 4096)
    finally:
        os.close(terminal)
        os.close(master)

    assert result.returncode == 7, (output, result.stderr)
    assert b"\x1b[200~" + DRAFT.encode() + b"\x1b[201~" in output
    assert result.stderr == b""


def test_ctrl_z_returns_to_zsh_and_fg_resumes_codex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is required")

    codex = tmp_path / "codex"
    codex.write_text(
        f"#!{sys.executable}\n"
        """\
import os
import signal
import sys
import termios
import tty

assert os.getpgrp() == os.tcgetpgrp(0)
shell_mode = termios.tcgetattr(0)
tty.setraw(0)
os.write(1, b"\\x1b]7501;state=idle:app=codex\\x1b\\\\")
received = b""
while not received.endswith(b"\\x1b[201~"):
    received += os.read(0, 4096)
os.write(1, b"codex-draft-ready\\n")
for _ in range(2):
    assert os.read(0, 1) == b"\\x1a"
    termios.tcsetattr(0, termios.TCSADRAIN, shell_mode)
    os.killpg(os.getpgrp(), signal.SIGTSTP)
    tty.setraw(0)
    os.write(1, b"codex-resumed\\n")
assert os.read(0, 1) == b"q"
sys.exit(7)
"""
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PS1", "review-shell> ")
    monkeypatch.setenv("TERM", "xterm-256color")

    shell, terminal = pty.fork()
    if shell == 0:
        os.execl(zsh, zsh, "-fi")

    output = b""

    def read_until(marker: bytes) -> None:
        nonlocal output
        deadline = time.monotonic() + 5
        while marker not in output:
            readable, _, _ = select.select(
                [terminal], [], [], max(0, deadline - time.monotonic())
            )
            assert readable, (marker, output)
            chunk = os.read(terminal, 4096)
            assert chunk, (marker, output)
            output += chunk
        _, output = output.split(marker, 1)

    try:
        prompt = b"review-shell> "
        read_until(prompt)
        os.write(terminal, b"unsetopt zle\n")
        read_until(prompt)
        command = shlex.join([sys.executable, str(SCRIPT), DRAFT])
        os.write(terminal, command.encode() + b"\n")
        read_until(b"codex-draft-ready")
        for _ in range(2):
            os.write(terminal, b"\x1a")
            read_until(b"suspended")
            read_until(prompt)
            assert termios.tcgetattr(terminal)[3] & termios.ICANON
            os.write(terminal, b"printf '%s%s\\n' shell- active\n")
            read_until(b"shell-active")
            read_until(prompt)
            os.write(terminal, b"fg\n")
            read_until(b"codex-resumed")
            assert not termios.tcgetattr(terminal)[3] & termios.ICANON
        os.write(terminal, b"q")
        read_until(prompt)
        os.write(terminal, b"printf '%s%d\\n' exit-code- $?\n")
        read_until(b"exit-code-7")
    finally:
        os.close(terminal)
        with suppress(ProcessLookupError):
            os.kill(shell, signal.SIGHUP)
        os.waitpid(shell, 0)
