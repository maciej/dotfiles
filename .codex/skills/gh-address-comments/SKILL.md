---
name: gh-address-comments
description: Address actionable GitHub pull request review feedback using gh. Use when Codex needs to inspect unresolved review threads, requested changes, inline comments, or top-level PR discussion and, when requested, implement the fixes locally.
---

# GitHub PR Review Follow-up

Treat review state as a thread-aware workflow. Flat PR comments do not reliably preserve resolution, outdated state, or inline anchors.

## Workflow

1. Resolve the PR from the user-provided URL or identifier, or from the current branch with `gh pr view --json number,url`.
2. Inspect the PR metadata and patch with `gh pr view` and `gh pr diff`.
3. Run the bundled helper whenever unresolved threads, inline locations, or resolution state matter:

```bash
python3 "<path-to-skill>/scripts/fetch_comments.py" --repo "<owner>/<repo>" --pr "<number-or-url>"
```

   With no arguments, the helper resolves the current branch PR.
4. Separate actionable unresolved feedback from resolved, outdated, informational, or duplicate comments. Group related feedback by behavior rather than treating every comment as an independent change.
5. Follow the requested scope:
   - For review or triage, report actionable feedback without editing.
   - For requested fixes, implement the clearly actionable items and surface only ambiguities that materially change behavior.
6. Run focused verification and summarize what was addressed, what remains, and why.

## GitHub Write Safety

- Do not infer permission to post replies, submit reviews, or resolve human-authored threads from permission to edit local code.
- When the user asks Codex to address bot-authored feedback and the fix is implemented, resolve the corresponding bot-authored thread. Treat accounts marked by GitHub as bots, such as Gemini Code Assist, as bot-authored.
- Resolve human-authored threads only when explicitly requested.
- Surface conflicting feedback or likely regressions before choosing between incompatible requests.
- If `gh` cannot resolve the PR, report the missing repository, PR, or authentication context precisely.
