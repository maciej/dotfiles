---
description: "{url} fix GitLab MR feedback, mergeability, and CI issues"
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
   - Fetch and inspect MR mergeability fields, including `merge_status`, `detailed_merge_status`, conflict state, source/target branches, and whether the source branch is behind the target branch.
   - Treat `cannot_be_merged`, merge conflicts, or source-branch drift behind target as actionable items, not just status to report.
4. Triage mergeability before anything else:
   - if the MR has merge conflicts, update the local branch from the target branch and resolve conflicts locally
   - if the source branch is behind the target branch and needs rebasing or merging, perform that local update unless the user explicitly asked not to
   - do not push unless the user explicitly asks
   - if mergeability cannot be fixed locally without destructive action or policy-sensitive history rewriting, stop and explain the blocker clearly
5. Fetch and review all MR feedback, including:
   - overview comments
   - inline comments
   - unresolved discussion threads
6. Triage CI status for the MR branch:
   - inspect latest pipeline(s) and failed jobs
   - identify root cause for each failing job when possible
   - separate actionable failures from likely flakes/external failures
7. Implement fixes in the local branch for all valid issues found:
   - reviewer-requested code changes
   - actionable CI failures
   - merge conflicts or branch drift that block merging
8. Run the most relevant local verification available after the fixes (tests/lint/build as applicable) for confidence.
9. Produce a clear handoff for the user that includes:
   - what was fixed
   - whether merge conflicts were resolved locally
   - whether the branch is now ready to push
   - any remaining blockers or uncertain items
   - suggested responses to each reviewer comment/discussion (including what changed, or why no code change was made)

Important constraints:
- Do not create a merge request.
- Do not push unless the user explicitly asks.
- Resolve problems in code, including merge conflicts when they can be handled locally and safely.
- Do not treat `merge_status: cannot_be_merged` as informational-only; it requires action or an explicit blocker report.
- Suggest concise reply text the user can post back to commenters.
- Do not mention that `glab` and `jq` were successfully validated or already installed in the response unless missing prerequisites blocked the workflow.
