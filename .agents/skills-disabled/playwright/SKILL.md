---
name: playwright
description: Automate browser workflows from the terminal with playwright-cli. Use when Playwright CLI is explicitly requested or its snapshots, traces, PDFs, or reproducible terminal workflow are preferable to available browser-control tools.
---

# Playwright CLI

Prefer the bundled wrapper so a global install is unnecessary:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"
"$PWCLI" --help
```

The wrapper requires `npx`. If it is unavailable, report the missing Node.js/npm prerequisite instead of installing global packages without permission.

## Workflow

1. Open the target page.
2. Take a snapshot to obtain current element references.
3. Interact using references from that snapshot.
4. Snapshot again after navigation or substantial DOM changes.
5. Capture screenshots, PDFs, or traces when they help verify the requested outcome.

```bash
"$PWCLI" open https://example.com
"$PWCLI" snapshot
"$PWCLI" click <ref>
"$PWCLI" snapshot
```

When a reference becomes stale, snapshot again rather than bypassing the accessibility model with arbitrary page code.

## Scope

- Use CLI commands for ad hoc browser automation.
- Create Playwright test files when the user requests durable tests or the repository workflow calls for them.
- Follow the target repository's artifact-location and dependency conventions.
- Use a headed browser when visual observation is materially useful.

Read [cli.md](references/cli.md) only for command details. Read [workflows.md](references/workflows.md) only for tracing, multi-tab, configuration, or troubleshooting patterns.
