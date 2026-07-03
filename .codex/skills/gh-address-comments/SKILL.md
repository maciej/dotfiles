---
name: gh-address-comments
description: Address actionable GitHub pull request review feedback using gh. Use when Codex needs to inspect unresolved review threads, requested changes, inline review comments, or top-level PR discussion, then implement selected fixes locally.
---

# GitHub PR Comment Handler

Use this skill when the user wants to work through requested changes on a GitHub pull request. Treat review-thread state as a `gh api graphql` workflow because standard PR comment output is flat and does not reliably preserve thread resolution, outdated state, and inline anchors.

## Requirements

- Run `gh auth status` before inspecting private PRs or performing write actions.
- Ask the user to run `gh auth login` if authentication fails.
- Resolve the PR from an explicit URL, `<owner>/<repo>` plus PR number, or the current branch with `gh pr view --json number,url`.

## Workflow

1. Resolve the PR.
   - If the user provides a PR URL, use it directly.
   - If the user provides a repository and PR number, pass both to `gh`.
   - If the request is about the current branch PR, use local git context plus `gh pr view --json number,url`.
2. Inspect review context with thread-aware reads.
   - Use `gh pr view <pr> --json number,title,state,isDraft,author,headRefName,baseRefName,reviewDecision,latestReviews,comments,files,url` for metadata.
   - Use `gh pr diff <pr>` for patch context.
   - Use `scripts/fetch_comments.py` whenever the task depends on unresolved review threads, inline review locations, or resolution state. The script fetches `reviewThreads`, `isResolved`, `isOutdated`, and file and line anchors.
3. Cluster actionable review threads.
   - Group comments by file or behavior area.
   - Separate actionable change requests from informational comments, approvals, already-resolved threads, outdated threads, and duplicates.
4. Confirm scope before editing.
   - Present numbered actionable threads with a one-line summary of the required change.
   - If the user did not ask to fix everything, ask which threads to address.
   - If the user asks to fix everything, interpret that as all unresolved actionable threads and call out anything ambiguous.
5. Implement the selected fixes locally.
   - Keep each code change traceable back to the thread or feedback cluster it addresses.
   - If a comment calls for explanation rather than code, draft the response instead of forcing a code change.
6. Summarize the result.
   - List which threads were addressed, which were intentionally left open, and what tests or checks support the change.

## Script Usage

```bash
python3 "<path-to-skill>/scripts/fetch_comments.py" --repo "<owner>/<repo>" --pr "<number-or-url>" > pr_comments.json
python3 "<path-to-skill>/scripts/fetch_comments.py" > pr_comments.json
```

The second form resolves the current branch PR through `gh pr view`.

## Write Safety

- Do not reply on GitHub or submit a review unless the user explicitly asks for that write action.
- Do not resolve human-authored review threads unless explicitly asked. If the user asks Codex to address a bot-authored discussion and Codex implements the fix, resolve that discussion; bot-authored means GitHub marks the author as a bot, such as Gemini Code Assist / `gemini-code-assist`.
- If review comments conflict with each other or would cause a behavioral regression, surface the tradeoff before making changes.
- If a comment is ambiguous, ask for clarification or draft a proposed response instead of guessing.
- Do not treat flat PR comments as a complete representation of review-thread state.
- If `gh` hits auth or rate-limit issues mid-run, ask the user to re-authenticate and retry.

## Fallback

If `gh` cannot resolve the PR cleanly, tell the user whether the blocker is missing repository scope, missing PR context, or CLI authentication, then ask for the missing repo or PR identifier or for a refreshed `gh` login.
