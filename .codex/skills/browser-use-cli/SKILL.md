---
name: browser-use-cli
description: Automate a browser with the browser-use CLI for navigation, interaction, screenshots, and extraction. Use when the user explicitly requests browser-use or terminal-driven browser automation and this CLI is preferable to an available in-app browser.
---

# Browser Use CLI

Use `browser-use --help` for the installed command surface and `browser-use doctor` for diagnostics. Do not duplicate the full CLI reference in context.

## Choose a Browser Mode

- Default local session: use for unauthenticated automation.
- `--headed`: use when visual observation helps debugging.
- `--profile <name>`: start from a temporary copy of an existing Chrome profile when its login state is needed. Treat cookies created in the copy as session-local unless verified otherwise.
- `--connect` or `--cdp-url <url>`: attach to a Chrome instance intentionally exposed over CDP.
- Cloud mode: use only when already configured or explicitly requested. Do not create or claim an external account automatically.

Keep the same `--session` and connection flags across commands unless the installed version persists them.

## Interaction Loop

1. Open the target page.
2. Run `state` to inspect the current URL, title, and element indices.
3. Interact using indices from the latest state.
4. Re-run `state` after navigation or substantial UI changes.
5. Verify the requested outcome with state, extracted data, or a screenshot.

```bash
browser-use open https://example.com
browser-use state
browser-use click <index>
browser-use input <index> "text"
browser-use state
```

Useful commands:

```bash
browser-use screenshot <path.png>
browser-use get text <index>
browser-use get html --selector "<selector>"
browser-use wait text "<text>"
browser-use tab list
browser-use tab switch <index>
browser-use sessions
```

Inspect intermediate output before choosing an element index. Re-inspect when an index becomes stale. Close and recreate a session only when diagnostics indicate that the session or daemon is broken.

## Authenticated and Parallel Work

List available profile names with `browser-use profile list`. Avoid exposing cookies, private addresses, credentials, or profile contents in output.

Use named sessions for independent browser contexts:

```bash
browser-use --session <name> open <url>
browser-use --session <name> state
```

Read `references/multi-session.md` only for parallel-session details. Read `references/cdp-python.md` only for advanced CDP control not covered by the CLI.

## Cleanup

Close sessions and tunnels created for the task when they are no longer needed:

```bash
browser-use --session <name> close
browser-use tunnel stop <port>
```

Omit `--session` for the default task-owned session. Do not close a pre-existing browser, shared session, or unrelated tunnel.
