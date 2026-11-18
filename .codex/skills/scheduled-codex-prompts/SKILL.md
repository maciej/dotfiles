---
name: scheduled-codex-prompts
description: Schedule, inspect, or cancel one-time follow-ups in a saved local Codex thread using Linux systemd user timers. Use for follow-ups that should run after the CLI closes.
---

# Scheduled Codex prompts

Confirm the target thread UUID and its working directory through the Codex thread list or current session context. Resolve the user's time to a full date, time, and IANA timezone. Keep the scheduled prompt self-contained, explicit about what to report in the thread, and within the authority the user granted. The prompt is stored on the local machine and becomes part of the thread when delivered.

Requires a running systemd user manager, Python 3.9 or newer, and a Codex CLI that supports `codex queue --resume`. Run the bundled helper with the prompt on stdin. Replace the thread UUID, workspace path, and time placeholders with values for your machine.

```sh
python3 ~/.codex/skills/scheduled-codex-prompts/scripts/schedule.py \
  --thread THREAD_UUID --cwd /absolute/workspace \
  --at 'YYYY-MM-DD HH:MM:SS Etc/UTC' <<'PROMPT'
Reply with TIMER-OK in this thread to confirm that the scheduled prompt arrived.
PROMPT
```

The helper creates one persistent user timer and prints its name and next trigger. Report the local time and target thread. If the machine is unavailable at the scheduled time, systemd can catch up when the user manager starts. Check `loginctl show-user "$USER" -p Linger` if operation after logout matters. Leave login and daemon settings as configured.

Inspect the timer with `systemctl --user status UNIT.timer`. After it fires, check `journalctl --user -u UNIT.service` and the target thread transcript. A successful queue command confirms acceptance of the message. The transcript confirms it ran. A resume warning can mean the message is already queued, so check the transcript before attempting another delivery. A smoke test can use a separate user-authorized test thread and a uniquely identifiable benign reply. Close its CLI before the timer fires to test unattended delivery.

To cancel an upcoming prompt, run `systemctl --user disable --now UNIT.timer`. To remove its files after cancellation or delivery, remove the matching `UNIT.timer`, `UNIT.service`, and `codex-scheduled-prompts/UNIT.json` under `${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user` and run `systemctl --user daemon-reload`. Disabling the timer only cancels a future trigger.
