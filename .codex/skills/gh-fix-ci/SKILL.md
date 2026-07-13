---
name: gh-fix-ci
description: Debug or fix failing GitHub Actions checks on a pull request using gh. Use when Codex needs to inspect PR checks and Actions logs, identify root causes, report a diagnosis, or implement a requested CI fix.
---

# GitHub Actions CI

## Workflow

1. Resolve the PR from the supplied identifier or the current branch. Check `gh auth status` when authentication is needed.
2. Inspect failing checks with the bundled helper:

```bash
python3 "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>"
```

   Add `--json` for structured output. The helper handles `gh` field drift and job-log fallbacks and exits nonzero while failures remain.
3. Read enough log context to identify the first actionable failure. Distinguish root causes from downstream failures and avoid over-claiming when logs are missing.
4. Treat non-GitHub Actions checks as external. Report their details URL unless the user asks to investigate that provider too.
5. Match the action to the request:
   - For diagnosis, summarize the failing check, evidence, likely cause, and smallest plausible fix.
   - For a requested fix, implement the focused change and run the most relevant local verification.
6. Recheck PR status when useful and report remaining failures, external checks, or flaky uncertainty.

## Manual Fallback

```bash
gh pr checks <pr> --json name,state,bucket,link,workflow
gh run view <run-id> --json name,workflowName,conclusion,status,url
gh run view <run-id> --log
```

Use `gh api` for job logs only when the standard commands do not expose them.

## Guardrails

- Do not change code merely to silence a failure that is unrelated to the local diff.
- Keep fixes tied to observed evidence and preserve repository-specific CI conventions.
- Report authentication, permissions, and unavailable logs as blockers rather than guessing.
