---
description: "{url} fix GitLab MR feedback and CI issues"
---

Address review feedback for a GitLab merge request.

Command arguments:
<arguments>
$ARGUMENTS
</arguments>

Start by loading the `gitlab` skill. Use it as the source of truth for `glab` usage and workflow details.

Then perform this workflow:

1. Resolve the target merge request:
   - if `$ARGUMENTS` includes an MR URL, use it
   - otherwise, default to the MR linked to the current branch if one exists
   - if neither is available, stop and ask the user for an MR URL
2. Validate prerequisites needed for the workflow (including `glab` and `jq`) and prompt for installation only if anything is missing.
3. Parse the target MR and confirm the current repository matches the MR project. If it does not, stop and ask the user to switch to the correct directory.
4. Fetch and review all MR feedback, including:
   - overview comments
   - inline comments
   - unresolved discussion threads
5. Triage CI status for the MR branch:
   - inspect latest pipeline(s) and failed jobs
   - identify root cause for each failing job when possible
   - separate actionable failures from likely flakes/external failures
6. Implement fixes in the local branch for valid review and CI issues.
7. Run the most relevant local verification available (tests/lint/build as applicable) for confidence.
8. Produce a clear handoff for the user that includes:
   - what was fixed
   - any remaining blockers or uncertain items
   - suggested responses to each reviewer comment/discussion (including what changed, or why no code change was made)

Important constraints:
- Do not create a merge request.
- Do not push unless the user explicitly asks.
- Resolve problems in code, and suggest concise reply text the user can post back to commenters.
- Do not mention that `glab` and `jq` were successfully validated or already installed in the response unless missing prerequisites blocked the workflow.
