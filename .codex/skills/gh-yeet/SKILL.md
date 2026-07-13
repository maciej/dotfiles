---
name: gh-yeet
description: "Publish local changes to GitHub using git and gh. Use only when the user explicitly wants the full flow: select intentional changes, create or keep a branch, commit, push, and open a pull request."
---

# Publish Changes to GitHub

## Workflow

1. Inspect `git status -sb` and the diff to establish the intended scope.
2. Choose the branch strategy from the user request and repository conventions. If the checkout is on the target default branch, create a focused branch; otherwise keep the current branch unless there is a concrete reason to switch.
3. Stage only intentional changes. Use explicit paths in a mixed worktree; use `git add -A` only when the entire worktree is confirmed in scope.
4. Run relevant checks that have not already been run, in proportion to the change.
5. Create a terse commit whose message describes the complete staged diff.
6. Push the current branch with upstream tracking.
7. Open the pull request with `gh pr create`:
   - Follow any repository template or user-specified title, body, base, and head.
   - Otherwise use a concise title and a short body covering the change and actual verification.
   - Create a ready PR by default; use draft only when requested or when the repository workflow clearly requires it.
   - Include the repository's issue-closing syntax when the change addresses a referenced issue.
8. Report the branch, commit, PR URL and target, validation, and any residual concern.

## Safety

- Require an accessible GitHub remote and authenticated `gh` session before remote writes.
- Never stage unrelated user changes or silently broaden a mixed-worktree scope.
- Do not invent repository naming or PR-body conventions when local guidance exists.
- Stop before pushing if intended scope cannot be determined safely.

Prefer a body file over shell-quoted multiline Markdown when the PR body contains code spans or other shell-sensitive text.
