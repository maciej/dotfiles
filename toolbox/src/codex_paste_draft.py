#!/usr/bin/env python3
"""Open the Codex TUI and paste an editable draft once its composer is ready."""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import signal
import socket
import sys
import termios
import tty
from collections.abc import Callable
from contextlib import suppress

# Codex emits this terminal status when it has an idle composer.
COMPOSER_IDLE = b"\x1b]7501;state=idle:app=codex\x1b\\"
BUFFER_SIZE = 65536


def relay(
    master: int, paste: bytes, job_control: socket.socket, suspend: Callable[[], None]
) -> bool:
    os.set_blocking(master, False)
    stdin_open = True
    job_control_open = True
    pending_input = bytearray()
    marker_tail = b""
    pasted = False

    while True:
        readers: list[int | socket.socket] = [master]
        if stdin_open and len(pending_input) < BUFFER_SIZE:
            readers.append(0)
        if job_control_open:
            readers.append(job_control)
        writers = [master] if pending_input else []
        readable, writable, _ = select.select(readers, writers, [])

        if master in readable:
            try:
                output = os.read(master, BUFFER_SIZE)
            except OSError as error:
                # Linux reports PTY EOF as EIO. Other systems return empty bytes.
                if error.errno != errno.EIO:
                    raise
                return pasted
            if not output:
                return pasted

            sys.stdout.buffer.write(output)
            sys.stdout.buffer.flush()
            if not pasted:
                status_output = marker_tail + output
                if COMPOSER_IDLE in status_output:
                    pending_input.extend(paste)
                    pasted = True
                marker_tail = status_output[-(len(COMPOSER_IDLE) - 1) :]

        # Show Codex's terminal reset before yielding the outer terminal.
        if job_control in readable:
            if job_control.recv(1):
                suspend()
                continue
            job_control_open = False

        if master in writable:
            try:
                written = os.write(master, pending_input)
            except BlockingIOError:
                pass
            else:
                del pending_input[:written]

        if 0 in readable:
            user_input = os.read(0, BUFFER_SIZE)
            pending_input.extend(user_input)
            stdin_open = bool(user_input)


def shell_status(status: int) -> int:
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return os.WEXITSTATUS(status)


def supervise_codex(job_control: socket.socket) -> int:
    # Keep a parent in the PTY's session, in a separate process group, so
    # Codex's foreground group can be stopped by SIGTSTP.
    start_read, start_write = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(start_write)
        job_control.close()
        ready = os.read(start_read, 1)
        os.close(start_read)
        if not ready:
            os._exit(127)
        os.execlp("codex", "codex")

    def signal_child(signum: int) -> None:
        with suppress(ProcessLookupError):
            os.killpg(child, signum)

    def hang_up(signum, _frame):
        signal_child(signum)
        signal_child(signal.SIGCONT)

    os.close(start_read)
    try:
        os.setpgid(child, child)
        signal.signal(signal.SIGHUP, hang_up)
        signal.signal(signal.SIGTERM, hang_up)
        os.tcsetpgrp(0, child)
        os.write(start_write, b"1")
    finally:
        os.close(start_write)

    while True:
        _, status = os.waitpid(child, os.WUNTRACED)
        if not os.WIFSTOPPED(status):
            return shell_status(status)

        try:
            job_control.sendall(b"S")
            resumed = bool(job_control.recv(1))
        except OSError:
            resumed = False
        if not resumed:
            signal_child(signal.SIGHUP)
        signal_child(signal.SIGCONT)


def launch(draft: str) -> int:
    original_mode = termios.tcgetattr(0)
    window_size = fcntl.ioctl(0, termios.TIOCGWINSZ, bytes(8))
    job_control, supervisor_control = socket.socketpair()
    supervisor, master = pty.fork()
    if supervisor == 0:
        job_control.close()
        try:
            fcntl.ioctl(0, termios.TIOCSWINSZ, window_size)
            os._exit(supervise_codex(supervisor_control))
        except OSError as error:
            os.write(2, f"codex-paste-draft: {error}\n".encode())
            os._exit(127)
    supervisor_control.close()

    def resize(_signum, _frame):
        size = fcntl.ioctl(0, termios.TIOCGWINSZ, bytes(8))
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)

    def stop(signum, _frame):
        raise SystemExit(128 + signum)

    def suspend() -> None:
        termios.tcsetattr(0, termios.TCSADRAIN, original_mode)
        os.kill(os.getpid(), signal.SIGTSTP)
        tty.setraw(0, termios.TCSANOW)
        resize(None, None)
        job_control.sendall(b"C")

    handlers = {
        signal.SIGWINCH: signal.signal(signal.SIGWINCH, resize),
        signal.SIGHUP: signal.signal(signal.SIGHUP, stop),
        signal.SIGTERM: signal.signal(signal.SIGTERM, stop),
    }
    paste = b"\x1b[200~" + draft.encode() + b"\x1b[201~"
    try:
        tty.setraw(0, termios.TCSANOW)
        resize(None, None)
        pasted = relay(master, paste, job_control, suspend)
    finally:
        try:
            termios.tcsetattr(0, termios.TCSADRAIN, original_mode)
        finally:
            for signum, handler in handlers.items():
                signal.signal(signum, handler)
            job_control.close()
            os.close(master)
            _, status = os.waitpid(supervisor, 0)

    if not pasted:
        print(
            f"codex-paste-draft: paste this draft into Codex manually:\n{draft}",
            file=sys.stderr,
        )
    return shell_status(status)


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].replace("\n", "").isprintable():
        print("Usage: codex-paste-draft <draft>", file=sys.stderr)
        return 2
    if not (os.isatty(0) and os.isatty(1)):
        print("codex-paste-draft: an interactive terminal is required", file=sys.stderr)
        return 1
    return launch(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
