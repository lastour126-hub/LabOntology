---
name: labontology
description: Use when a user needs to prepare, check, continue, or safely maintain a laboratory workflow through natural-language conversation.
---

# LabOntology

Help users move a laboratory task forward safely. Treat ordinary descriptions of an experiment, a readiness concern, an interrupted task, or a requested action as the starting point; users do not need to know the workflow library or command names.

## Conversation-first workflow

1. Understand the experiment goal and whether the user is preparing, checking readiness or progress, maintaining the workflow library, or requesting an action.
2. Before reading a workflow directory or importing it, run `resolve-cache` for that directory and workspace. Do not import when a valid matching cache is found: inspect or run the resolved cache instead.
3. Import only when no valid matching cache exists, or when the user explicitly asks to refresh, update, or reimport the workflow library. A task data file is not a reason to rebuild the workflow-library cache unless the user says it changes the library itself.
4. Explain the result in laboratory language: recommended next step, available procedure, missing prerequisite, current task state, and any approval needed.
5. Do not ask the user to choose a command or expose cache, graph, Skill, or Runtime terminology unless they are maintaining the library or ask for technical detail.

## Task situations

### Prepare or plan an experiment

Inspect the available procedures and start or resume a task for the stated goal. State what is ready, what is missing, and the next safe step.

### Check readiness or progress

Check the workflow library and any existing task. Report only the relevant procedures, source freshness, missing conditions, and current progress.

### Maintain the workflow library

When the user explicitly adds, updates, refreshes, or asks to validate laboratory procedures, import or refresh the collection and report whether it is complete and valid. Technical paths and cache details are appropriate in this situation. Do not treat a spreadsheet, sample description, reagent list, or other task input as a workflow-library update.

### Request an action

Confirm only a routine read-only check that is eligible under the recorded policy. Explain why a device-facing, high-impact, stale, or evidence-incomplete action requires the approval path instead.

## Internal command routing

Use `scripts/labontology.py` from this Skill directory only when the conversation requires it. For any existing workflow directory, first call `resolve-cache --skill-root <directory> --workspace <workspace>` and include `--suite-id` when the suite is known. A successful result is authoritative: use its `cache_dir` with `inspect`, `run`, `status`, or `decide`; do not call `import`. Call `import` only after resolution reports no valid matching cache or after the user explicitly requests a refresh, update, or reimport. Keep command output as evidence for the response rather than presenting it as the user interface.

## Safety boundary

Never auto-execute device-facing or significant actions, invent missing evidence, or override Runtime policy. `run` creates task context; it does not execute laboratory work. Use `scripts/runtime.py` only for advanced recovery or Agent-directed operations outside the release entrypoint's routine read-only boundary.
