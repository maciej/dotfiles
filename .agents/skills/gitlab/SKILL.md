---
name: gitlab
description: Load before running any glab commands to ensure correct CLI syntax. Use when creating/viewing MRs, checking pipelines, managing issues, or any GitLab operations (when remote contains "gitlab").
---

# GitLab Workflow

Use the `glab` CLI for GitLab repositories, merge requests, issues, and CI/CD.

## Resolve GitLab Context

Determine the GitLab host before running `glab`:

1. Prefer the current repository remote:
   ```bash
   git remote -v | rg -i gitlab
   ```
2. If there is no GitLab remote, use `$GITLAB_HOST`.
3. If the user provided a GitLab URL, extract the hostname from it.

If no GitLab host or repository context can be determined, this skill does not apply.

## Operating Modes

- **Repository work**: Create MRs, manage CI, review code, and update branches from a directory with a GitLab remote.
- **Investigation**: Search issues, MRs, projects, or code from any directory when `glab` has a host from `$GITLAB_HOST`, `-R`, or the user-provided URL.

## Agent Rules

- Verify the GitLab remote or host first; do not run repository-scoped `glab` commands in a non-GitLab repo.
- Use `--yes` for MR create/update/merge commands when available so agentic tooling does not hang on confirmation prompts.
- Prefer explicit polling over live CI watching: check with `glab ci status`, then `glab ci list` or the pipeline URL until the pipeline reaches a terminal state.
- Pull logs immediately on failure with `glab ci trace <job-name-or-id>`; the log usually contains the actionable error.
- Retry likely flakes once with `glab ci retry <job-name-or-id>`. If it fails again, treat it as real.
- Pipe `glab api` responses through `jq` or redirect them when only the side effect matters; full JSON responses are often large.
- On `HTTP 429`, back off and retry after a delay; pace bulk API/comment workflows. Read `references/rate-limits.md` only when debugging limit behavior.
- On auth errors, run `glab auth status`; ask the user before starting a login/install flow.
- Use `glab <command> --help` for ordinary command syntax. Keep this skill for local gotchas, fragile flows, and reusable helpers.

## Common MR Flow

```bash
glab mr create --fill --target-branch main --yes
glab mr create --draft --fill --yes
glab mr update <id> --ready --yes
```

Use `--draft` for WIP and `glab mr update <id> --ready` when it is ready for review. Reference issues explicitly in descriptions: `Closes #123` to auto-close, `Relates to #123` for tracking only.

For less common clone, issue, release, search, and MR command examples, read `references/REFERENCE.md`.

## Bundled Helpers

### Recent MR Activity

Use this helper for compact recent-MR summaries without falling back to `glab api`:

```bash
scripts/recent-mrs.py --hours 24
scripts/recent-mrs.py --hours 24 --json
scripts/recent-mrs.py --repo group/project --hours 48
```

If `--hours` is omitted, it uses `72` on Mondays to cover Friday plus the weekend, and `24` on other days.

### Review Queue

Use this helper to list non-draft MRs assigned to you for review, excluding MRs you already approved:

```bash
scripts/review-queue.py <gitlab-host>
scripts/review-queue.py <gitlab-host> --json
scripts/review-queue.py <gitlab-host> --user <username>
```

The GitLab API cannot filter "not approved by me" directly, so the helper checks each MR's approvals.

## Code Review Notes

View context:

```bash
glab mr diff <id>
glab mr view <id> --comments
glab mr note list <id> --state unresolved
glab mr note list <id> -F json | jq '.[].notes[] | {id, body}'
```

Approve:

```bash
glab mr approve <id>
```

If approving an already-approved MR returns `401 Unauthorized`, treat it as "already approved" rather than a permissions failure.

When posting or replying to MR comments or inline discussions with text you composed in your own words, prefix the body with `✨ `. Do not add the prefix when using user-dictated wording or refining text the user already wrote.

Add a general MR comment:

```bash
glab mr note create <id> -m "Overall this looks good. One architectural question: ..."
```

Remove yourself as reviewer:

```bash
glab mr update <id> --reviewer=-username --yes
```

The `@me` shorthand does not work with the `-` prefix; use the actual GitLab username.

### Inline Discussions

Prefer inline discussions when feedback targets a specific line. Inline discussions require diff position SHAs:

```bash
glab api "projects/<owner>%2F<repo>/merge_requests/<mr-iid>/versions" \
  | jq '.[0] | {base_commit_sha, head_commit_sha, start_commit_sha}'
```

Create the discussion with JSON input; `-f` bracket syntax is unreliable for nested `position` objects:

```bash
cat <<'EOF' | glab api "projects/<owner>%2F<repo>/merge_requests/<mr-iid>/discussions" \
  -X POST -H "Content-Type: application/json" --input -
{
  "body": "Your comment here",
  "position": {
    "base_sha": "<base_commit_sha>",
    "start_sha": "<start_commit_sha>",
    "head_sha": "<head_commit_sha>",
    "position_type": "text",
    "old_path": "path/to/file.py",
    "new_path": "path/to/file.py",
    "old_line": null,
    "new_line": 42
  }
}
EOF
```

For removed lines, set `old_line` and `new_line: null`. For unchanged context lines, set both. Verify success by checking that the note has `type: "DiffNote"` and a non-null `position`.

### Reply and Resolve

`glab mr note` creates general comments unless you target a discussion. Use `glab mr note list` to find the discussion or note ID, then reply through the discussions API:

```bash
glab api "projects/<owner>%2F<repo>/merge_requests/<mr-iid>/discussions/<discussion-id>/notes" \
  -X POST \
  -f body="Your reply message"

glab mr note resolve <note-or-discussion-id> <mr-iid>
glab mr note reopen <note-or-discussion-id> <mr-iid>
```

Resolve only after the feedback is fully addressed.

## CI/CD

```bash
glab ci status
glab ci list
glab ci trace <job-name-or-id>
glab ci retry <job-name-or-id>
glab ci run
glab job artifact <ref> <job-name>
```

When a pipeline fails, read `references/ci-troubleshooting.md` for the remediation workflow and common failure patterns.

## References

- `references/REFERENCE.md`: less common GitLab command examples and API patterns
- `references/ci-troubleshooting.md`: failed pipeline remediation
- `references/rate-limits.md`: GitLab rate-limit behavior and optional local config
