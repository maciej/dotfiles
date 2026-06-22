---
name: gh-yeet
description: "Publish local changes to GitHub using git and gh: confirm scope, create or keep the branch, stage intentional changes, commit, push, and open a ready-to-review pull request unless the user asks for a draft PR."
---

# GitHub Publish Changes

Use this skill only when the user explicitly wants the full publish flow from the local checkout: branch setup if needed, staging, commit, push, and opening a pull request.

## Requirements

- Require GitHub CLI `gh`. Check `gh --version`. If missing, ask the user to install `gh` and stop.
- Require an authenticated `gh` session. Run `gh auth status`. If unauthenticated, ask the user to run `gh auth login` before continuing.
- Require a local git repository with a clear understanding of which changes belong in the PR.

## Naming Conventions

- Branch for repositories owned by the authenticated `gh` user: `{description}`.
- Branch for repositories owned by another account or organization: `{gh-user}/{description}`.
- Commit: `{description}` in terse imperative or noun-phrase form.
- PR title: `{description}` summarizing the full diff. Do not add a standard automation prefix.
- PR state: ready to review by default. Use a draft PR only when the user explicitly asks for draft.

To decide which branch convention applies, resolve the authenticated user with:

```bash
gh api user --jq .login
```

Then resolve the target repository owner with:

```bash
gh repo view --json nameWithOwner
```

If the target repository owner matches the authenticated user, use `{description}`. If it differs, prefix the branch with the authenticated user, as `{gh-user}/{description}`. Keep `{description}` short, lowercase, hyphen-separated, and specific to the change.

## Workflow

1. Confirm intended scope.
   - Run `git status -sb` and inspect the diff before staging.
   - If the working tree contains unrelated changes, do not default to `git add -A`; ask which files belong in the PR.
2. Determine the branch strategy.
   - Resolve the remote default branch with `gh repo view --json defaultBranchRef` when needed.
   - If on `main`, `master`, or the remote default branch, create a new branch using the convention above.
   - Otherwise stay on the current branch.
3. Stage only the intended changes.
   - Prefer explicit file paths when the worktree is mixed.
   - Use `git add -A` only when the user has confirmed the whole worktree belongs in scope.
4. Commit tersely with the confirmed description.
5. Run the most relevant checks available if they have not already been run.
   - If checks fail due to missing dependencies or tools, install what is needed and rerun once.
6. Push with tracking:

```bash
git push -u origin "$(git branch --show-current)"
```

7. Open the PR with `gh pr create`.
   - Derive the base branch from the user request when specified; otherwise use the remote default branch.
   - Use `--title` with the plain PR title and `--body-file` with a temp file containing real Markdown newlines.
   - Omit `--draft` by default so the PR is ready for review.
   - Add `--draft` only when the user explicitly asked for a draft PR.
   - Use `--head "$(git branch --show-current)"` unless a fork or cross-repo target requires an explicit owner-qualified head.
8. Summarize the result with branch name, commit, PR target, validation, and anything the user still needs to confirm.

## Write Safety

- Never stage unrelated user changes silently.
- Never push without confirming scope when the worktree is mixed.
- Do not create a draft PR unless the user explicitly asks for one.
- If the repository does not appear to be connected to an accessible GitHub remote, stop and explain the blocker before making assumptions.

## PR Body Expectations

Use the concise Codex app style: exactly two sections, `Summary` and `Verification`.

```markdown
## Summary
- ...
- ...

## Verification
- `command`
- Not run (reason)
```

Keep the body short:

- Use 1-3 bullets under `Summary`.
- Use one bullet per verification command or result.
- Include only checks actually run.
- If no checks were run, write `- Not run (reason)` under `Verification`.
- Do not add extra sections such as root cause, impact, screenshots, or follow-ups unless the user explicitly asks.
