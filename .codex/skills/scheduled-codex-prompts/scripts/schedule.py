#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def systemctl(*args):
    subprocess.run(["systemctl", "--user", *args], check=True)


def unit_argument(value):
    return json.dumps(str(value), ensure_ascii=False).replace("%", "%%").replace("$", "$$")


def deliver(payload_path):
    task = json.loads(Path(payload_path).read_text())
    codex = task["codex"]
    subprocess.run([codex, "app-server", "daemon", "start"], check=True)
    os.execv(codex, [
        codex, "queue", "--cd", task["cwd"], "--thread", task["thread"],
        "--resume", "--message", task["prompt"],
    ])


def schedule():
    parser = argparse.ArgumentParser(description="Schedule a one-time prompt read from stdin.")
    parser.add_argument("--thread", type=UUID, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--at", required=True, metavar="'YYYY-MM-DD HH:MM:SS TIMEZONE'")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [A-Za-z0-9_+/-]+", args.at):
        parser.error("--at requires an exact date, time, and IANA timezone")
    local_time, zone_name = args.at.rsplit(" ", 1)
    try:
        zone = ZoneInfo(zone_name)
        when = datetime.fromisoformat(local_time).replace(tzinfo=zone)
    except (ValueError, ZoneInfoNotFoundError) as error:
        parser.error(str(error))
    if when.timestamp() <= datetime.now().timestamp():
        parser.error("--at must be in the future")

    codex = shutil.which("codex")
    if not codex or not args.cwd.is_absolute() or not args.cwd.is_dir():
        parser.error("codex must be on PATH and --cwd must be an existing absolute directory")
    prompt = sys.stdin.read().strip()
    if not prompt or "\x00" in prompt:
        parser.error("stdin must contain a nonempty prompt without NUL bytes")

    subprocess.run(["systemd-analyze", "calendar", args.at], check=True)
    queue_help = subprocess.check_output([codex, "queue", "--help"], text=True)
    if "--resume" not in queue_help:
        parser.error("this Codex CLI does not support queue --resume")
    unit_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd/user"
    payload_dir = unit_dir / "codex-scheduled-prompts"
    payload_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = f"codex-prompt-{uuid4().hex[:16]}"
    payload = payload_dir / f"{name}.json"
    timer = unit_dir / f"{name}.timer"
    service = unit_dir / f"{name}.service"
    command = " ".join(map(unit_argument, [sys.executable, Path(__file__).resolve(), "--deliver", payload]))

    enabled = False
    try:
        payload_fd = os.open(payload, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(payload_fd, "w") as handle:
            json.dump({"codex": codex, "cwd": str(args.cwd), "thread": str(args.thread), "prompt": prompt}, handle)
        service.write_text(
            "[Unit]\nDescription=Send a scheduled Codex prompt\n\n"
            f"[Service]\nType=oneshot\nExecStart={command}\n"
        )
        timer.write_text(
            "[Unit]\nDescription=Run a one-time Codex follow-up\n\n"
            f"[Timer]\nOnCalendar={args.at}\nAccuracySec=1s\nPersistent=true\n\n"
            "[Install]\nWantedBy=timers.target\n"
        )
        systemctl("daemon-reload")
        systemctl("enable", "--now", timer.name)
        enabled = True
    finally:
        if not enabled:
            subprocess.run(["systemctl", "--user", "disable", "--now", timer.name], check=False)
            for path in (timer, service, payload):
                path.unlink(missing_ok=True)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print(timer.name, flush=True)
    systemctl("show", timer.name, "-p", "ActiveState", "-p", "NextElapseUSecRealtime")


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("Scheduled Codex prompts require Linux with a systemd user manager.")

    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--deliver":
            deliver(sys.argv[2])
        else:
            schedule()
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
