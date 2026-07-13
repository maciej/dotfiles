---
name: github
description: Triage and operate GitHub repositories, pull requests, issues, reviews, labels, reactions, and Actions workflows using gh. Use for general GitHub context and route focused publish, review-follow-up, or CI work to the corresponding specialist skill.
---

# GitHub

Resolve repository context from the user-provided URL or identifier, or from the current checkout. Use `gh auth status` when private data or a write requires authentication.

## Direct Work

Use `gh pr`, `gh issue`, and `gh repo` for repository orientation, metadata, diffs, lists, comments, labels, reactions, and summaries. Use `gh api` or GraphQL only when the standard commands omit required state.

For read requests, return the relevant state and likely next action. For writes, apply only the requested mutation to the resolved target and verify it with a read-back.

## Route Focused Work

- Unresolved review threads or requested changes: use `../gh-address-comments/SKILL.md`.
- Failing GitHub Actions checks and logs: use `../gh-fix-ci/SKILL.md`.
- Branch, stage, commit, push, and pull request publishing: use `../gh-yeet/SKILL.md`.

Do not force a specialist flow when a simple `gh` read or narrow mutation fully satisfies the request.

## Useful Orientation

```bash
gh repo view --json nameWithOwner,defaultBranchRef,url
gh pr view <pr> --json number,title,state,isDraft,headRefName,baseRefName,reviewDecision,url
gh issue view <issue> --json number,title,body,state,labels,comments,url
```

If repository or item scope remains ambiguous after local inspection, ask for the missing identifier rather than operating on a guess.
