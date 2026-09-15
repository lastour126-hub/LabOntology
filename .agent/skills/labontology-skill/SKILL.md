---
name: labontology
description: Use when a user needs to prepare, check, continue, or safely maintain a laboratory workflow through natural-language conversation.
---

# LabOntology

Help users move a laboratory task forward safely. Treat ordinary descriptions of an experiment, a readiness concern, an interrupted task, or a requested action as the starting point; users do not need to know the workflow library or command names.

## Conversation-first workflow

1. Understand the experiment goal and whether the user is preparing, checking readiness or progress, maintaining the workflow library, or requesting an action.
2. Each laboratory workspace has one workspace cache and one unified graph. Before planning, run `resolve-cache` for the relevant Skill root and explicit Suite when one is known. It verifies both the tracked file hashes and the current Skill-library inventory, so added, removed, moved, or changed Skill sources make the scoped cache stale. If current, reuse the one workspace cache. Only when stale or unavailable, synchronize the workspace Skill root for the same Suite; a current synchronization is a no-op and never creates another cache. In a mixed root, update only the Suite needed for the task; a newly discovered, unclassified Skill is added only to `suite:general`, never copied into existing Suites.
3. A `SkillSuite` is an explicit semantic collection inside the unified graph, not a cache directory and not an Agent-inferred project label. Unclassified or general Skills belong to `suite:general`; do not invent FDU, IB, OASIS, or another Suite from a Skill's name or prose. A task data file is not a reason to rebuild the workflow-library cache unless the user says it changes the library itself.
4. Explain the result in laboratory language: recommended next step, available procedure, missing prerequisite, current task state, and any approval needed.
5. Do not ask the user to choose a command or expose cache, graph, Skill, or Runtime terminology unless they are maintaining the library or ask for technical detail.

## User-facing response contract

Every response should lead with the laboratory outcome, then give only the next useful step.

- **Ready:** say what procedure is available and what can happen next.
- **Missing condition:** name the missing material, file, capability, or evidence and ask for only that item.
- **Waiting for approval:** state the proposed action, its impact, and the exact confirmation needed.
- **Paused task:** identify the matching task, its current state, and what will be restored; do not imply that a device action will be repeated automatically.
- **Library problem:** say “实验流程库需要更新” or equivalent before giving technical detail.

Do not expose raw tracebacks, filesystem internals, cache paths, or command flags in ordinary conversation. If several projects or tasks match, present their human-readable names and ask one focused disambiguation question. Keep technical identifiers available only as a secondary detail for maintenance or troubleshooting.

## Task situations

### Prepare or plan an experiment

Inspect the available procedures and start or resume a task for the stated goal. State what is ready, what is missing, and the next safe step.

Example: “我找到样品处理流程。当前缺少离心机可用性确认；补充后我会继续检查下一项。”

When the user describes experimental steps in natural language, treat that description as the primary flow input. Extract the proposed steps and matching Skills, show a short draft sequence, and ask for confirmation before treating it as a formal flow. Do not infer one complete flow merely because several Skills share a Suite.

### Check readiness or progress

Check the workflow library and any existing task. Report only the relevant procedures, source freshness, missing conditions, and current progress.

Example: “昨天的任务停在等待确认，已保留此前的输入和结果。下一步是确认是否继续该检查。”

### Maintain the workflow library

When the user explicitly adds, updates, refreshes, or asks to validate laboratory procedures, synchronize the workspace graph and report whether it is complete and valid. Technical paths and cache details are appropriate in this situation. Do not treat a spreadsheet, sample description, reagent list, or other task input as a workflow-library update.

If the user supplies or confirms a sequence, preserve its wording and order as user-confirmed workflow evidence. If no sequence or dependency is available, keep the Skills as a searchable collection rather than presenting an inferred execution order.

### Request an action

Confirm only a routine read-only check that is eligible under the recorded policy. Explain why a device-facing, high-impact, stale, or evidence-incomplete action requires the approval path instead.

Example: “这是只读检查，不会修改实验设备。确认后我会执行并返回检查结果。”

## Internal command routing

Use `scripts/labontology.py` from this Skill directory only when the conversation requires it. For an available Skill root, call `resolve-cache --skill-root <directory> --workspace <workspace>` first; if it reports stale or unavailable, call `sync --skill-root <directory> --workspace <workspace>` and resolve again. Use `sync --all` only when the user explicitly asks to refresh the whole mapped library; it refreshes each existing Suite without assigning a new Skill to it, then adds any unclassified new Skill only to `suite:general`. The result identifies the authoritative one workspace cache; use it with `inspect`, `run`, `resume`, `status`, `missions`, or `decide`. Use `describe-skill` only after a compact candidate is selected and full instructions, inputs, evidence, or safety constraints are needed. Include `--suite-id` whenever the relevant Suite is explicit; it scopes a unified graph and never selects another cache. A mission records its selected Suite, so a repeated request such as “continue yesterday's experiment” should use `missions --query <goal words>` before `status` or `resume`; resume will restore that recorded scope. Keep command output as evidence for the response rather than presenting it as the user interface.

## Safety boundary

Never auto-execute device-facing or significant actions, invent missing evidence, or override Runtime policy. `run` creates task context; it does not execute laboratory work. Use `scripts/runtime.py` only for advanced recovery or Agent-directed operations outside the release entrypoint's routine read-only boundary.
