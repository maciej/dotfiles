---
name: obsidian-cli
description: Interact with a running Obsidian app using its CLI to read, create, search, and manage vault content or to develop and debug plugins and themes. Use for Obsidian vault operations and Obsidian-specific development workflows.
---

# Obsidian CLI

Use `obsidian help` as the current command reference. Obsidian must be running.

## Syntax and Targeting

- Pass valued parameters as `key=value`; quote values containing spaces.
- Pass boolean flags without a value.
- Use `file=<name>` for wikilink-style resolution or `path=<vault-relative-path>` for an exact path.
- Commands target the most recently focused vault by default. Put `vault=<name>` first when a specific vault matters.
- Use `silent` when a command should not open the affected note.

```bash
obsidian read file="My Note"
obsidian create name="New Note" content="# Hello" silent
obsidian append path="Projects/Plan.md" content="- [ ] Follow up"
obsidian search query="search term" limit=10
obsidian property:set name="status" value="done" file="My Note"
```

Inspect `obsidian help <command>` before using unfamiliar or potentially destructive commands.

## Plugin and Theme Development

After a code change:

1. Reload the plugin or theme.
2. Read app errors and relevant console output.
3. Verify the affected behavior with a screenshot, DOM query, or CSS inspection.
4. Repeat only as needed to clear observed failures.

```bash
obsidian plugin:reload id=<plugin-id>
obsidian dev:errors
obsidian dev:console level=error
obsidian dev:screenshot path=<path.png>
obsidian dev:dom selector="<selector>" text
```

Use `obsidian eval` only when the regular CLI cannot expose the required state, and keep evaluated code scoped to the task.
