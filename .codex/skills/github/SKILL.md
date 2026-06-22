---
name: github
description: Triage and operate GitHub repository, pull request, issue, and Actions workflows using the local gh CLI. Use when Codex needs GitHub context, PR or issue summaries, review or comment inspection, labels, reactions, or routing to focused publish, review-follow-up, or CI debugging flows.
---

# GitHub

Use this skill as the umbrella entrypoint for GitHub work. Resolve the repository context first, gather the requested state with `gh`, then route to a narrower skill as soon as the task is clearly about publishing changes, addressing review feedback, or debugging CI.

## Requirements

- Require GitHub CLI `gh`. Run `gh --version` if availability is uncertain.
- Require authentication for private repos or write actions. Run `gh auth status` and ask the user to run `gh auth login` if it fails.
- Prefer local git context for requests about "this branch", "this PR", or the current checkout.

## Responsibilities

Handle these directly when the request does not need a narrower workflow:

- repository orientation and remote/default-branch discovery
- recent PR or issue triage
- PR and issue metadata summaries
- PR patch inspection with `gh pr diff`
- PR comments, reviews, labels, and reactions
- issue lookup and summarization
- PR creation after a branch is already pushed

Useful commands:

```bash
gh repo view --json nameWithOwner,defaultBranchRef,url
gh pr list --state open --json number,title,author,isDraft,reviewDecision,mergeStateStatus,updatedAt,url
gh pr view <pr> --json number,title,body,state,isDraft,author,headRefName,baseRefName,reviewDecision,statusCheckRollup,labels,url
gh pr diff <pr>
gh issue list --state open --json number,title,author,labels,updatedAt,url
gh issue view <issue> --json number,title,body,state,author,labels,comments,url
```

Use `gh api` or `gh api graphql` when the standard `gh pr` and `gh issue` commands do not expose the needed field.

## Routing Rules

1. Resolve the operating context:
   - If the user provides a repository, PR number, issue number, or URL, use that.
   - If the request is about the current branch or current PR, resolve local git context and use `gh pr view --json number,url`.
   - If the repository is still ambiguous after local inspection, ask for the repo identifier.
2. Classify the request:
   - `repo or PR triage`: summarize PRs, issues, patches, comments, labels, reactions, or repository state.
   - `review follow-up`: unresolved review threads, requested changes, or inline review feedback.
   - `CI debugging`: failing checks, Actions logs, or CI root-cause analysis.
   - `publish changes`: create or switch branches, stage changes, commit, push, and open a ready-to-review PR.
3. Route immediately when a specialist path is clear:
   - Review comments and requested changes: `../gh-address-comments/SKILL.md`
   - Failing GitHub Actions checks: `../gh-fix-ci/SKILL.md`
   - Commit, push, and open PR: `../gh-yeet/SKILL.md`

## Default Workflow

1. Resolve repository and item scope.
2. Gather GitHub state with `gh`.
3. Decide whether the task stays in triage or needs a specialist skill.
4. Route immediately when the work becomes review follow-up, CI debugging, or publishing.
5. End with a concise summary of what was inspected, what changed, and what remains.

## Output Expectations

- For triage requests, return the relevant repository, PR, or issue state and the next likely action.
- For mixed requests, tell the user which specialist path you are taking and why.
- For write actions, restate the exact PR, issue, label, reaction, or branch target before applying the change.
- Treat GitHub Actions log retrieval as a `gh` workflow; use `gh run view` or `gh api` as needed.

## Examples

- "Use GitHub to summarize the open PRs in this repo and tell me what needs attention."
- "Help with this PR."
- "Review the latest comments on PR 482 and tell me what is actionable."
- "Debug the failing checks on this branch."
- "Commit these changes, push them, and open a PR."
