---
name: skill-refine
description: Review a completed Codex session for durable procedural lessons and propose or apply focused reusable-skill updates.
---

# Skill Refine

Use this skill when the user asks to distill a completed Codex session into reusable
procedural guidance, review what was learned, or refine an existing skill.

This is a skill review, not a memory review. Codex's native memory layer owns general
facts about the user and general preferences. Do not inspect, edit, or propose changes
to memory stores as part of this skill. A preference may belong in a task-specific
skill only when it changes the procedure for that class of work.

Default to proposal-only mode. Do not edit a skill unless the user explicitly asks to
apply, implement, or go ahead with the proposed changes. Do not infer write, commit,
or push authorization from a request to review.

## Review the evidence

Read the completed conversation and identify only lessons supported by what actually
happened. A candidate is useful when it is one or more of:

- a non-trivial workflow, tool sequence, fix, or decision process that completed successfully;
- a user correction to the workflow or task-specific output that should prevent repetition;
- a missing, misleading, or outdated step in a skill that was used or consulted;
- a generalizable pitfall paired with the mechanism that causes it.

Prefer a verified working path. If the session ended without a working method, do not
turn the failed attempts into guidance. If a problem was caused by setup state, capture
the verified fix rather than claiming the tool or feature is permanently broken.

## Choose the smallest durable target

Search the available skill roots with `rg --files -g 'SKILL.md'` and inspect likely
matches before selecting a target.

Use this order:

1. Patch the relevant skill that was loaded or consulted in the session.
2. Patch another existing class-level skill that covers the workflow.
3. Add a focused supporting reference, template, or verification script under an
   existing umbrella when that is the right home.
4. Create a new class-level skill only when no existing skill covers the reusable class
   of work.

Before changing an existing `SKILL.md` or supporting file, read its current contents
and preserve unrelated guidance. Treat bundled, third-party, symlinked, or externally
owned skills as read-only unless the user explicitly names the exact target and asks
for that change.

## Write durable guidance

Keep the target concise and procedure-first:

- Put steps in execution order, including concrete commands, tools, and decision points.
- Express pitfalls as imperative, generalizable rules with a short explanation of why.
- Put always-applicable rules in `SKILL.md`; put occasional topical depth in a focused
  `references/` file and link it from the entrypoint.
- Strengthen an existing rule instead of adding a duplicate. Edit a misleading sentence
  in place instead of appending a contradictory correction.
- Keep the skill name at the class level. Never name it after a date, incident, PR,
  issue, error string, feature codename, or one-off task.

Do not capture secrets, raw logs, temporary paths, dates, ticket numbers, one-off task
narratives, unresolved failures, environment-dependent errors, or permanent negative
claims about tools. Do not restate `AGENTS.md`, tool schemas, or generic agent advice.

## Propose or apply

If there is no durable procedural lesson, report `Nothing to save.`

Otherwise, report:

- the proposed target skill or supporting file;
- the evidence and why the lesson generalizes;
- the exact content change or unified diff;
- any overlapping skill that should be consolidated later.

In proposal-only mode, stop after showing the diff. When the user explicitly authorizes
the change, use `apply_patch`, inspect the resulting diff, and run the bundled
`quick_validate.py` validator when creating or substantially revising a skill. Report
the files changed and validation result; leave commits, pushes, and other publication
actions to the user's explicit request.
