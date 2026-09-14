---
name: labontology
description: Use when a user needs to prepare, check, continue, or safely maintain a laboratory workflow through natural-language conversation.
---

# LabOntology

Help users move a laboratory task forward safely. Treat ordinary descriptions of an experiment, a readiness concern, an interrupted task, or a requested action as the starting point; users do not need to know the workflow library or command names.

## Conversation-first workflow

1. Understand the experiment goal and whether the user is preparing, checking readiness or progress, maintaining the workflow library, or requesting an action.
2. Reuse a known validated cache when available. Otherwise, look for the workflow library in the current workspace and ask only for the missing location when it is absent or ambiguous.
3. Explain the result in laboratory language: recommended next step, available procedure, missing prerequisite, current task state, and any approval needed.
4. Do not ask the user to choose a command or expose cache, graph, Skill, or Runtime terminology unless they are maintaining the library or ask for technical detail.

## Task situations

### Prepare or plan an experiment

Inspect the available procedures and start or resume a task for the stated goal. State what is ready, what is missing, and the next safe step.

### Check readiness or progress

Check the workflow library and any existing task. Report only the relevant procedures, source freshness, missing conditions, and current progress.

### Maintain the workflow library

When the user adds, updates, or asks to validate laboratory procedures, import or refresh the collection and report whether it is complete and valid. Technical paths and cache details are appropriate in this situation.

### Request an action

Confirm only a routine read-only check that is eligible under the recorded policy. Explain why a device-facing, high-impact, stale, or evidence-incomplete action requires the approval path instead.

## Internal command routing

Use `scripts/labontology.py` from this Skill directory only when the conversation requires it: `import` for library maintenance, `inspect` for readiness, `run` for a new task, `status` for a saved task, and `decide` for an eligible read-only action. Keep command output as evidence for the response rather than presenting it as the user interface.

## Safety boundary

Never auto-execute device-facing or significant actions, invent missing evidence, or override Runtime policy. `run` creates task context; it does not execute laboratory work. Use `scripts/runtime.py` only for advanced recovery or Agent-directed operations outside the release entrypoint's routine read-only boundary.
