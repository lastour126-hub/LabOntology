---
name: labontology
description: Use when a user needs to prepare, check, continue, or safely maintain a laboratory workflow through natural-language conversation.
---

# LabOntology

Help users move a laboratory task forward safely. Treat ordinary descriptions of an experiment, a readiness concern, an interrupted task, or a requested action as the starting point; users do not need to know the workflow library or command names.

## Conversation-first workflow

1. Understand the experiment goal and whether the user is preparing, checking readiness or progress, maintaining the workflow library, or requesting an action.
2. Each laboratory workspace has one workspace cache and one unified graph. Before planning, run `resolve-cache` for the relevant Skill root and explicit Suite when one is known. It verifies both the tracked file hashes and the current Skill-library inventory, so added, removed, moved, or changed Skill sources make the scoped cache stale. If current, reuse the one workspace cache. Only when stale or unavailable, synchronize the workspace Skill root for the same Suite; a current synchronization is a no-op and never creates another cache.
3. A `SkillSuite` is an explicit semantic collection inside the unified graph, not a cache directory and not an Agent-inferred project label. Unclassified or general Skills belong to `suite:general`; do not invent FDU, IB, OASIS, or another Suite from a Skill's name or prose. A task data file is not a reason to rebuild the workflow-library cache unless the user says it changes the library itself.
4. Explain the result in laboratory language: recommended next step, available procedure, missing prerequisite, current task state, and any approval needed.
5. Do not ask the user to choose a command or expose cache, graph, Skill, or Runtime terminology unless they are maintaining the library or ask for technical detail.

## Task situations

### Prepare or plan an experiment

Inspect the available procedures and start or resume a task for the stated goal. State what is ready, what is missing, and the next safe step.

### Check readiness or progress

Check the workflow library and any existing task. Report only the relevant procedures, source freshness, missing conditions, and current progress.

### Maintain the workflow library

When the user explicitly adds, updates, refreshes, or asks to validate laboratory procedures, synchronize the workspace graph and report whether it is complete and valid. Technical paths and cache details are appropriate in this situation. Do not treat a spreadsheet, sample description, reagent list, or other task input as a workflow-library update.

### Request an action

Confirm only a routine read-only check that is eligible under the recorded policy. Explain why a device-facing, high-impact, stale, or evidence-incomplete action requires the approval path instead.

## Internal command routing

Use `scripts/labontology.py` from this Skill directory only when the conversation requires it. For an available Skill root, call `resolve-cache --skill-root <directory> --workspace <workspace>` first; if it reports stale or unavailable, call `sync --skill-root <directory> --workspace <workspace>` and resolve again. Use `sync --all` only for a known mixed root that has already been explicitly mapped to multiple Suites; it refreshes each recorded Suite and never infers a new one. The result identifies the authoritative one workspace cache; use it with `inspect`, `run`, `resume`, `status`, `missions`, or `decide`. Use `describe-skill` only after a compact candidate is selected and full instructions, inputs, evidence, or safety constraints are needed. Include `--suite-id` whenever the relevant Suite is explicit; it scopes a unified graph and never selects another cache. A mission records its selected Suite, so a repeated request such as “continue yesterday's experiment” should use `missions --query <goal words>` before `status` or `resume`; resume will restore that recorded scope. Keep command output as evidence for the response rather than presenting it as the user interface.

## Safety boundary

Never auto-execute device-facing or significant actions, invent missing evidence, or override Runtime policy. `run` creates task context; it does not execute laboratory work. Use `scripts/runtime.py` only for advanced recovery or Agent-directed operations outside the release entrypoint's routine read-only boundary.
