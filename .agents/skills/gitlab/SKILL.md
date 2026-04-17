---
name: gitlab
description: Load before running any glab commands to ensure correct CLI syntax. Use when creating/viewing MRs, checking pipelines, managing issues, or any GitLab operations (when remote contains "gitlab").
---

# GitLab Workflow

Work with GitLab repositories, merge requests, issues, and CI/CD pipelines using the `glab` CLI.

## FIRST: Determine GitLab Host

Resolve which GitLab instance to use (in priority order):

1. **Current repository remote** (highest priority)
   ```bash
   git remote -v | grep -i gitlab
   ```
   Extract hostname from remote URL (e.g., `gitlab.example.com` from `git@gitlab.example.com:org/repo.git`)

2. **GITLAB_HOST environment variable**
   ```bash
   echo $GITLAB_HOST
   ```
   Use if no GitLab remote exists in current directory

3. **Deduce from context**
   If user provides a GitLab URL, extract the hostname from it.
   Example: `https://gitlab.example.com/org/repo/-/merge_requests/123` → use `gitlab.example.com`

If none of the above apply and no GitLab context can be determined, this skill doesn't apply.

## Usage Modes

This skill supports two modes:

- **Repository work**: Creating MRs, managing CI, reviewing code. Requires being in a directory with a GitLab remote.
- **Investigation**: Searching issues/MRs/code across GitLab projects. Works from any directory with `glab` configured (via `GITLAB_HOST` or prior authentication).

## Key Guidelines

- **Verify remote first**: No GitLab remote = don't use `glab`
- **Check CI before requesting review**: Run `glab ci status` after pushing and re-check with `glab ci list` or the pipeline URL until the pipeline actually finishes. Fix failures before requesting reviews.
- **Do not rely on live CI watching mode**: It can be misleading for long-running pipelines. Prefer explicit polling with non-live commands.
- **Pull logs immediately on failure**: Run `glab ci trace <job-name>` first. The logs contain the answer.
- **Use draft MRs for WIP**: Create with `--draft`, mark ready with `glab mr update <id> --ready`
- **Reference issues explicitly**: Use `Closes #123` for auto-close, `Relates to #123` for tracking only
- **Retry flaky failures, fix real ones**: Retry a job with `glab ci retry <job-name>`. If it fails again, it's a real issue.
- **Always use `--yes` for MR creation**: Include `--yes` to skip the submission confirmation prompt. Interactive mode doesn't work with agentic tooling.
- **Filter API output**: `glab api` calls return full JSON responses (often 300KB+). Always pipe through `jq` to extract needed fields, or redirect to `/dev/null` if you only care about the side effect.

## Rate Limits

GitLab instances may enforce rate limits on API and web requests. AI agents making many sequential requests can hit these easily.

### Detection

GitLab returns **HTTP 429 Too Many Requests** when a rate limit is exceeded.

GitLab also returns `RateLimit-*` response headers (`RateLimit-Remaining`, `Retry-After`, etc.), but `glab api` does not surface these by default. Use `glab api -i` to inspect headers if you need to debug rate-limit issues, but do not rely on header monitoring during normal operation.

**Caveat**: GitLab has both infrastructure-level and application-level rate limits (e.g. issue creation, project export). Application-level limits are not reflected in response headers.

### Best Practices

1. **Handle 429 reactively**: On HTTP 429, back off and retry after a delay (start with 30s, double on repeated 429s)
2. **Pace bulk operations**: When making many sequential API calls (e.g. posting inline review comments), add a brief pause between requests
3. **Retry on transient 500/503**: These may occur when limits engage; retry once with backoff before treating as a real error
4. **Minimize request count**: Use `jq` to extract needed fields from a single response rather than making multiple narrower requests

### Optional Local Config

If `config.json` exists in the skill root, use its `rate_limits` values as instance-specific hints.

```json
{
  "rate_limits": {
    "authenticated_api": { "max_requests": 36000, "period": "1 hour" },
    "authenticated_web": { "max_requests": 36000, "period": "1 hour" },
    "sustained_requests_per_second_hint": 10,
    "low_remaining_threshold": 1000
  }
}
```

Treat every field as optional. Missing `config.json` or missing keys are not errors; continue with the generic 429/backoff guidance above.

For portable guidance and public GitLab limits, see `references/rate-limits.md`.

## Quick Start: Branch → MR

The most common workflow—create a branch, make changes, open an MR:

```bash
git checkout -b <branch-name>
# make changes
git add . && git commit -m "<your commit message>"
git push -u origin <branch-name>
glab mr create --fill --target-branch main --yes
```

## Quick Reference: CI Commands

| Task | Command |
|------|---------|
| Check pipeline status | `glab ci status` |
| List pipelines | `glab ci list` |
| Pull job logs | `glab ci trace <job-name>` |
| Retry failed job | `glab ci retry <job-name>` |
| Run new pipeline | `glab ci run` |
| Download artifacts | `glab job artifact <ref> <job-name>` |

## Prerequisites

This skill requires the `glab` CLI. If `glab` commands fail with "command not found", ask the user to install it:

```bash
# macOS
brew install glab

# Linux (Debian/Ubuntu)
sudo apt install glab

# Other methods: https://gitlab.com/gitlab-org/cli#installation
```

Authentication must be configured. Run `glab auth status` to check. If not authenticated:

```bash
glab auth login
```

---

# Detailed Reference

## Repository Setup

### Clone a Repository

```bash
# Clone via glab (uses authenticated user context)
glab repo clone <owner>/<repo>

# Clone with specific branch
glab repo clone <owner>/<repo> -- --branch <branch>

# Clone to specific directory
glab repo clone <owner>/<repo> <directory>
```

### Fork a Repository

```bash
# Fork to your namespace
glab repo fork <owner>/<repo>

# Fork and clone immediately
glab repo fork <owner>/<repo> --clone
```

### View Repository Info

```bash
glab repo view
glab repo view <owner>/<repo>
```

## Branch and Changes

Follow your team's conventions for branch names and commit messages (e.g., `PROJ-123: description`, conventional commits, or other formats).

### Create a Branch

```bash
git checkout -b <branch-name>
# Make changes, stage, and commit
git add .
git commit -m "<your commit message>"
```

### Push Branch

```bash
git push -u origin <branch-name>
```

## Merge Request Operations

### Create a Merge Request

```bash
# With specific options
glab mr create \
  --title "feat: add new feature" \
  --description "$(cat <<'EOF'
Your description here (supports markdown)
EOF
)" \
  --target-branch main \
  --assignee @me \
  --label "enhancement" \
  --yes

# Create as draft
glab mr create --draft --title "WIP: feature in progress" --yes

# Create and auto-fill from commits
glab mr create --fill --yes
```

### List Merge Requests

```bash
# List open MRs (default)
glab mr list

# List by state
glab mr list --merged      # merged MRs only
glab mr list --closed      # closed MRs only
glab mr list --all         # all MRs (open, merged, closed)

# Filter by author or assignee
glab mr list --author @me
glab mr list --assignee @me

# Filter by label
glab mr list --label bug,urgent

# Limit results
glab mr list --per-page 10
```

### View Merge Request Details

```bash
# View current branch's MR
glab mr view

# View specific MR
glab mr view 123
```

### Update a Merge Request

```bash
# Update title
glab mr update 123 --title "new title"

# Add labels
glab mr update 123 --label "reviewed,approved"

# Change assignees
glab mr update 123 --assignee user1,user2

# Mark ready for review (remove draft)
glab mr update 123 --ready

# Add reviewers
glab mr update 123 --reviewer user1,user2
```

### Merge a Merge Request

```bash
# Merge when pipeline succeeds
glab mr merge 123 --yes

# Attempt the merge now instead of enabling auto-merge
glab mr merge 123 --auto-merge=false --yes

# Squash and merge
glab mr merge 123 --squash --yes

# Delete source branch after merge
glab mr merge 123 --remove-source-branch --yes
```

### Check Out an MR Locally

```bash
# Check out MR branch locally for testing/review
glab mr checkout 123
```

## Code Review

This section applies when **giving** or **receiving** code reviews. Both workflows share common commands but differ in intent and process.

### Giving Code Reviews

When reviewing someone else's MR, outcomes include:

| Outcome | When to use |
|---------|-------------|
| **Approve** | Code is good to merge, or only has minor nits |
| **Comment without approval** | Changes needed before merge |
| **Remove self as reviewer** | Wrong person, or delegating to someone else |

**Prefer inline discussions** over general comments when feedback targets specific lines or code blocks. Inline discussions anchor the comment to the exact location, making it easier for the author to address. Use general MR comments for architectural feedback, overall approach questions, or praise.

**Review queue**: To get MRs pending your review, run:

```bash
scripts/review-queue.py <gitlab-host>
```

Options:
- `--json`: Output as JSON (easier for programmatic processing)
- `--user <name>`: Check another user's queue

This script lists MRs where you're a reviewer, excluding drafts and MRs you've already approved. The GitLab API doesn't support "not approved by me" filtering, so the script checks each MR's approval status individually.

#### Review Process

The agent can assist with code reviews in several ways:

1. **First pass**: Agent reviews the diff and drafts suggested comments
2. **Refinement**: User writes initial comments, agent refines wording or adds detail
3. **Combined**: Agent does first pass, user adjusts, agent finalizes

#### Viewing the Diff

```bash
# View diff for current branch's MR
glab mr diff

# View diff for specific MR
glab mr diff 123

# View MR details with discussion context
glab mr view 123 --comments
```

#### Approving

```bash
glab mr approve 123
```

You can approve an MR even after leaving nit comments—this signals "good to merge once you've addressed these minor points."

**Caveat**: Approving an MR you've already approved returns `401 Unauthorized`—this is not a permissions error, it means you already approved. When processing multiple MRs, either check approval status first via the approvals API, or treat 401 as "already approved" rather than a failure.

#### Creating Inline Discussions (Diff Notes)

Inline discussions require position information. First, get the diff version SHAs:

```bash
glab api "projects/<owner>%2F<repo>/merge_requests/<mr-iid>/versions" \
  | jq '.[0] | {base_commit_sha, head_commit_sha, start_commit_sha}'
```

Then create the inline discussion using JSON input (**note**: the `-f` bracket syntax doesn't work reliably for nested position objects):

```bash
cat << 'EOF' | glab api "projects/<owner>%2F<repo>/merge_requests/<mr-iid>/discussions" \
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

**Position fields**:
- `new_line`: Line number in the new version (for added/modified lines). Set `old_line: null`.
- `old_line`: Line number in the old version (for removed lines). Set `new_line: null`.
- Both `old_line` and `new_line`: For context lines (unchanged).

**Verification**: A successful inline comment has `type: "DiffNote"` and non-null `position`. If you get `type: "DiscussionNote"` with `position: null`, the position was malformed.

#### Creating General Comments

For feedback not tied to specific code:

```bash
glab mr note 123 -m "Overall this looks good. One architectural question: ..."
```

#### Removing Yourself as Reviewer

```bash
glab mr update 123 --reviewer=-username
```

Note: The `@me` shorthand does not work with the `-` prefix. Use your actual GitLab username.

### Receiving Code Reviews

When addressing feedback on your own MR, there are two common scenarios:

1. **Specific MR**: Pull comments from a particular MR by ID
2. **Current branch MR**: Address comments on the MR for your current working branch (more typical)

#### Process

1. **Understand the feedback**: Fetch and read all comments
2. **Plan the response**: For each comment, decide to:
   - Make the requested change
   - Reply with clarification or pushback
   - Create a follow-up ticket for larger scope items
3. **Implement changes**: Make code amendments locally
4. **Reply to threads**: Acknowledge feedback, explain changes made
5. **Resolve discussions**: Mark threads as resolved once fully addressed

#### Fetching Comments

```bash
# View comments on current branch's MR
glab mr view --comments

# View comments on specific MR
glab mr view 123 --comments

# List discussions with filters or JSON output (experimental)
glab mr note list 123 --state unresolved
glab mr note list 123 -F json | jq '.[].notes[] | {id, body}'
```

#### Replying to Discussion Threads

`glab mr note` creates general MR comments only. Use `glab mr note list` to inspect discussions, then use the discussions API to reply to a specific thread:

```bash
# 1. Find discussion ID from note ID
glab mr note list 123 -F json \
  | jq '.[] | select(.notes[].id == <note-id>) | .id'

# 2. Post reply to the thread
glab api "projects/<owner>%2F<repo>/merge_requests/<mr-iid>/discussions/<discussion-id>/notes" \
  -X POST \
  -f body="Your reply message"

# 3. Resolve the discussion after addressing feedback
glab mr note resolve <note-id> 123

# 4. Reopen the discussion later if needed
glab mr note reopen <note-id> 123
```

`glab mr note list`, `resolve`, and `reopen` are currently marked experimental in `glab`, so fall back to the API only if those subcommands misbehave on your host.

**When to resolve**: Resolve the discussion only when fully addressed—you made the fix, answered the question, or created a follow-up ticket. Do *not* resolve if you asked a clarifying question or promised changes still pending.

## CI/CD Monitoring and Failure Remediation

CI job failures are the most common blocker for merging MRs.

### Check Pipeline Status

```bash
# Quick status check for current branch
glab ci status

# List recent pipelines with status
glab ci list

# Check status for a specific MR
glab mr view 123  # Shows pipeline status in MR details
```

Prefer repeated non-live checks when waiting for completion.

**Pipeline states**: `pending`, `running`, `success`, `failed`, `canceled`, `skipped`

### Pull Job Logs

```bash
# Stream logs from a running or completed job
glab ci trace <job-name>
```

### When a Pipeline Fails

For troubleshooting failed pipelines—identifying failed jobs, analyzing logs, common failure patterns, retry vs fix decisions—see [references/ci-troubleshooting.md](references/ci-troubleshooting.md).

## Searching GitLab

### Search Issues

```bash
# Search in current project
glab issue list --search "bug in login"

# Search by label
glab issue list --label "bug"

# Search across all accessible projects (use API)
glab api "search?scope=issues&search=login+error" | jq '.[] | {id, title, web_url}'
```

### Search Merge Requests

```bash
# Search in current project
glab mr list --search "refactor auth"

# Search across GitLab (use API)
glab api "search?scope=merge_requests&search=auth+refactor" | jq '.[] | {id, title, web_url}'
```

### Search Code/Projects

```bash
# Search for projects
glab api "search?scope=projects&search=my-library" | jq '.[] | {id, name, web_url}'

# Search code (blobs)
glab api "search?scope=blobs&search=deprecated+function" | jq '.[] | {path, project_id, ref}'
```

## Additional Reference

For less common operations (multi-repo workflows, issues, releases, API access, CI debugging, artifacts), see [references/REFERENCE.md](references/REFERENCE.md).

## Additional Notes

- **Check authentication on errors**: If `glab` commands fail with 401/403, run `glab auth status` and re-authenticate with `glab auth login`.
- **Branch naming**: Follow your team's conventions (e.g., `feature/`, `fix/`, `$USER/`, or project-specific prefixes).
