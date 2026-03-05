---
description: "{url} fix GitLab MR feedback and CI issues"
---

Address review feedback for a GitLab merge request.

Merge request URL:
$ARGUMENTS

Start by loading the `gitlab` skill. Use it as the source of truth for `glab` usage and workflow details.

Then perform this workflow:

1. Validate prerequisites needed for the workflow (including `glab` and `jq`) and prompt for installation if missing.
2. Parse the MR URL and confirm the current repository matches the MR project. If it does not, stop and ask the user to switch to the correct directory.
3. Fetch and review all MR feedback, including:
   - overview comments
   - inline comments
   - unresolved discussion threads
4. Triage CI status for the MR branch:
   - inspect latest pipeline(s) and failed jobs
   - identify root cause for each failing job when possible
   - separate actionable failures from likely flakes/external failures
5. Implement fixes in the local branch for valid review and CI issues.
6. Run the most relevant local verification available (tests/lint/build as applicable) for confidence.
7. Produce a clear handoff for the user that includes:
   - what was fixed
   - any remaining blockers or uncertain items
   - suggested responses to each reviewer comment/discussion (including what changed, or why no code change was made)

Important constraints:
- Do not create a merge request.
- Do not push unless the user explicitly asks.
- Resolve problems in code, and suggest concise reply text the user can post back to commenters.
