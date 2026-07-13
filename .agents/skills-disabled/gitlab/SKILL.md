---
name: gitlab
description: Operate GitLab repositories, merge requests, issues, reviews, and CI with glab. Use when the target is a GitLab host or repository and GitLab-specific context, mutations, or troubleshooting are required.
---

# GitLab

## Resolve Context

Resolve the host and project from a user-provided URL, an explicit `-R` target, or the current repository remote. Use `$GITLAB_HOST` only when no project remote is needed. Do not run repository-scoped commands against an unrelated checkout.

Use `glab auth status` when authentication is required and `glab <command> --help` for the installed syntax.

## General Workflow

1. Resolve the host, project, and item identifier.
2. Read the relevant merge request, issue, pipeline, or job state.
3. Match the action to the request: report for read-only work; mutate only when the user requested the corresponding change.
4. Prefer non-interactive flags such as `--yes` when available.
5. Verify writes with a read-back and summarize the resulting state.

Avoid passing Markdown containing backticks directly through shell-quoted arguments. Use `--fill`, stdin, `--input -`, or a temporary body file.

## Merge Requests and Reviews

```bash
glab mr view <id>
glab mr diff <id>
glab mr view <id> --comments
glab mr note list <id> --state unresolved
glab mr create --fill --target-branch <branch> --yes
```

Use inline discussions when feedback targets a specific diff line. Read [REFERENCE.md](references/REFERENCE.md) for the required diff-position SHA and API payload only when creating or replying to inline discussions.

When following up on review feedback:

- distinguish actionable unresolved discussion from resolved, outdated, or informational comments;
- implement requested local fixes and run focused checks when the user asked for changes;
- do not infer permission to push, post, resolve, approve, or merge from permission to edit locally;
- resolve a discussion only after its feedback is fully addressed and the user has authorized that GitLab write.

## CI

```bash
glab ci status
glab ci list
glab ci trace <job-name-or-id>
```

Read the failing job log before proposing a fix. Use [ci-troubleshooting.md](references/ci-troubleshooting.md) for deeper remediation patterns. Retry a suspected flake only when retrying is within scope; do not use a retry as a substitute for diagnosis.

On rate limits, pace requests and read [rate-limits.md](references/rate-limits.md) only when limit behavior needs investigation.

## Bundled Helpers

Use `scripts/recent-mrs.py` for compact recent-MR activity and `scripts/review-queue.py` for non-draft merge requests assigned to the current reviewer but not yet approved:

```bash
scripts/recent-mrs.py --hours 24
scripts/review-queue.py <gitlab-host>
```

Both support `--json`; use their help for optional repository and user filters.
