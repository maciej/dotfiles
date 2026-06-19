---
name: gh-fix-ci
description: Debug or fix failing GitHub Actions checks on a pull request using gh. Use when Codex needs to inspect PR checks, retrieve Actions logs, identify root causes, propose a focused fix, and implement only after approval.
---

# GitHub Actions CI Fix

Use this skill when the task is specifically about failing GitHub Actions checks on a pull request.

## Requirements

- Authenticate with GitHub CLI once, then confirm with `gh auth status`.
- Require repo and workflow scopes for Actions inspection.
- Use `gh` for PR metadata, check status, Actions run metadata, and logs.

## Inputs

- `repo`: path inside the repo, default `.`
- `pr`: PR number or URL, optional; defaults to current branch PR
- `gh` authentication for the repo host

## Quick Start

```bash
python3 "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>"
python3 "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>" --json
```

## Workflow

1. Verify `gh` authentication.
   - Run `gh auth status` in the repo.
   - If unauthenticated, ask the user to run `gh auth login` with repo and workflow scopes before proceeding.
2. Resolve the PR.
   - If the user provides a PR number or URL, use that directly.
   - Otherwise prefer the current branch PR with `gh pr view --json number,url`.
   - Use `gh pr view <pr> --json number,title,state,isDraft,headRefName,baseRefName,url` for PR metadata.
   - Use `gh pr diff <pr>` when patch context matters to the diagnosis.
3. Inspect failing GitHub Actions checks.
   - Preferred: run the bundled script, which handles `gh` field drift and job-log fallbacks:

```bash
python3 "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "<number-or-url>"
```

   - Add `--json` for machine-friendly output.
   - Manual fallback:

```bash
gh pr checks <pr> --json name,state,bucket,link,startedAt,completedAt,workflow
gh run view <run_id> --json name,workflowName,conclusion,status,url,event,headBranch,headSha
gh run view <run_id> --log
gh api "/repos/<owner>/<repo>/actions/jobs/<job_id>/logs" > "<path>"
```

4. Scope non-GitHub Actions checks.
   - If a details URL is not a GitHub Actions run, label it as external and only report the URL.
   - Do not attempt Buildkite or other external providers unless the user explicitly wants a separate investigation path.
5. Summarize failures for the user.
   - Provide the failing check name, run URL when available, and a concise log snippet.
   - Call out missing logs explicitly and do not over-claim certainty.
6. Propose a focused fix plan and wait for approval.
   - Keep the plan tied directly to the failing checks and observed root cause.
7. Implement after approval.
   - Apply the approved fix locally.
   - Run the most relevant local verification available.
8. Recheck status and summarize residual risk.
   - Suggest re-running the relevant tests and `gh pr checks`.
   - Report what remains unverified, what may still be flaky, and whether any failing checks were external.

## Bundled Resources

### scripts/inspect_pr_checks.py

Fetch failing PR checks, pull GitHub Actions logs, and extract a failure snippet. Exits non-zero when failures remain so it can be used in automation.

Usage examples:

```bash
python3 "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "123"
python3 "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --pr "https://github.com/org/repo/pull/123" --json
python3 "<path-to-skill>/scripts/inspect_pr_checks.py" --repo "." --max-lines 200 --context 40
```

## Guardrails

- Treat non-GitHub Actions providers as report-only unless the user explicitly wants a separate investigation path.
- If the failure is clearly unrelated to the local diff, say so before proposing code changes.
