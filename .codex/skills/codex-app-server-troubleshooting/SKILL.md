---
name: codex-app-server-troubleshooting
description: Diagnose and restore local Codex app-server workspace access on macOS, especially when an external volume returns Operation not permitted, Rex or the desktop app already has disk access, or a detached server survived a CLI upgrade.
---

# Troubleshoot Codex app-server disk access on macOS

## Isolate the failure

1. Use the failing Codex session to open a known, non-sensitive file in the original checkout. Compare it with a readable local file and check that the external volume is mounted and writable with `diskutil info`. File metadata can be visible even when macOS denies reading the contents.
2. If the normal shell is sandboxed, repeat the same read once with approved Codex escalation. A denial there is evidence of a restriction outside the command sandbox. Check macOS privacy attribution before changing either permission layer. Read any existing TCC log evidence carefully. A cached denial may produce no fresh log entry.
3. Identify the app server for this session. Follow the command's process ancestry, and confirm the server owns the socket this client uses before considering a restart. Several Codex and terminal processes may coexist.

Useful read-only checks once `app_server_pid` is known:

```sh
ps -p "$app_server_pid" -o pid=,ppid=,lstart=,tty=,comm=
lsof -a -p "$app_server_pid" -d txt -Fn
lsof -a -p "$app_server_pid" -U -Fn
command -v codex
codex --version
codex app-server daemon version
```

Check whether the running executable path from `lsof` still exists. Homebrew may have replaced a binary while an old server kept running, sometimes leaving its mapped executable under a vanished `.upgrading` path. Compare the running server, managed package, and installed CLI versions separately. A stale binary is a clue. Verify the access boundary with a fresh launch.

## Compare launch contexts

TCC grants follow the macOS responsible process. The Unix parent PID can be `launchd` after detachment. A grant to the desktop app or Rex Server applies according to macOS attribution. Use TCC attribution logs if available. For a read-only diagnostic on macOS versions that expose the private lookup symbol, compare the responsible PID with the expected app:

```sh
python3 - "$app_server_pid" <<'PY'
import ctypes
import sys

system = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
lookup = getattr(system, "responsibility_get_pid_responsible_for_pid", None)
if lookup is None:
    sys.exit("Responsibility lookup unavailable on this macOS version")
lookup.argtypes = (ctypes.c_int,)
lookup.restype = ctypes.c_int
print(lookup(int(sys.argv[1])))
PY
```

Use `ps` on the returned PID to identify the app. Compare reading the exact same file from a shell freshly launched by the expected host. For Rex, use a separate short-lived Rex pane with the `rex` skill or local CLI help. If useful, start a short-lived `codex app-server --listen stdio://` from that shell and test `fs/readFile` after the app-server initialization handshake. Generate the protocol schema with the installed CLI when the parameters are uncertain. Compare this result with the failing server before changing anything.

If the intended responsible app lacks access, open **System Settings → Privacy & Security → Files & Folders** and have the user grant **Removable Volumes** for that app. Prefer this scoped grant. If the intended launcher already works, relaunch the affected server from that launcher. [Apple’s macOS file access guide](https://support.apple.com/guide/mac-help/control-access-to-files-and-folders-on-mac-mchld5a35146/mac)

## Recover and verify

- Before replacing a shared server, check for other active work and explain that restarting the server used by this session briefly disconnects its clients. Arrange the restart and a verification log outside that server, for example in a Rex pane.
- Inspect `codex app-server daemon --help` on the installed version. Use the managed restart workflow for a managed server. A running status alone does not establish managed ownership. If the CLI reports an unmanaged server, preserve its listener and relevant startup flags, verify the exact PID against the live socket, and arrange a graceful stop and replacement from the correct launcher. Preserve default listener syntax such as `--listen unix://` when it is how the existing control socket is selected. Treat a forced stop as a last resort within the approved restart scope.
- Verify that the replacement is listening on the expected socket and reports the intended running version. Reopen the original file through that server or through a reconnected Codex session. If workspace editing is in scope, create a unique temporary file in the original checkout, read it back, remove it, and check the working tree. A successful read from the standalone test server only establishes access in that launch context.
- If access remains denied after relaunch, report the observed process attribution and the failing access path. Recheck the scoped macOS grant for that process.

[Codex CLI reference](https://learn.chatgpt.com/docs/cli/reference)
