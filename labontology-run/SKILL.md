---
name: labontology-run
description: Use when an Agent needs to pursue a laboratory task, acquire or verify knowledge, choose and invoke Skills, interpret observations, adapt the next action, or request a human decision based on uncertainty, evidence authenticity, or operational impact.
---

# LabOntology Agent Runtime

The host Agent is the planner. It loops through goal, evidence, next Skill, action, observation and replanning. Knowledge retrieval, literature search, analysis, experiment design and device operations are all registered Skills. Python executes one selected action and persists the result; it does not infer the next action or follow a fixed line by default.

## Read the compact cache

Use the active suite cache's `cache-manifest.json`, `ontology.jsonl` and `source-index.json`. The graph is the only canonical normalized knowledge source. Query Skill contracts, artifacts, capabilities, evidence, unresolved fields, policies and optional workflow references from it. Read a selected Skill's source `SKILL.md` or KB through the external path/hash in `source-index.json` when detailed instructions are needed. Do not recreate or expect `Skills/`, `Graph/`, `Workflow/` or `DeviceKnowledge/` directories.

## Agent loop

1. Parse the user goal, success conditions, constraints and existing authorization.
2. Run `context` to inspect every registered candidate Skill and the current mission observations. Treat workflow edges as suggestions, not a required order.
3. Decide which one Skill most reduces the current information or execution gap. Prefer a knowledge or verification Skill before an uncertain device action.
4. Submit one decision with `act`. Include a reason and action assessment: `impact` (`routine` or `significant`), rationale, uncertainty list and authenticity-gap list. For a process Skill whose context includes `instruction_source`, first read that current `SKILL.md` and include its path and SHA-256 as `reviewed_instruction`; Agent-mode Skills do not need this receipt.
5. Inspect output, logs, evidence and source hashes. A successful process is not scientific validation; determine whether its result satisfies the current objective.
6. Return to decision-making after every result. Skills can be repeated, skipped, reordered or replaced. Submit `complete` only when evidence supports the user's success conditions.

`awaiting_decision` means the host Agent should reason again. It does not ask the user to orchestrate routine steps. A missing Skill or contract is reported as a graph/data gap for Creator; if a registered knowledge Skill can resolve the gap, invoke it first.

## Human decisions

Ask the user only for the specific current action when the Agent cannot establish a material fact, source authenticity is missing and cannot be verified, or an operation has significant impact and existing authorization does not cover its exact scope. Cached `unresolved` or low confidence fields are signals to assess, not automatic approval gates.

Use `request_human` for a question or a Skill decision assessment for an action. Record the concrete missing fact, impact and scope. A factual answer returns to Agent reasoning; scoped approval resumes only that action. Each later action is assessed again.

## Completion, failure and recovery

Agent Skills may complete without output files. Use `resume --agent-completed` for a successful zero-output action, `--summary` and `--evidence` for textual results, and `--agent-failed --summary` for failure. Declared output files must exist; never fabricate placeholders. Process failure or timeout becomes an observation and does not trigger a blind retry.

Context exposes `retry_candidates` only for failed read-only process actions explicitly marked retryable and still below their retry limit. The host Agent may retry one by submitting a normal `skill` decision with `"retry_of": "action:N"`; Runtime never creates a retry itself.

An interrupted `running` process must be reconciled before the next decision. Use `reconcile` with external evidence and one of `not_started`, `succeeded`, `failed` or `unknown`. Reconciliation records the conclusion without calling the Skill or a device API. A reconciled success must provide every declared output artifact; uncertain and failed outcomes cannot provide outputs. Device-facing and significant actions are never runtime-retry candidates.

## Commands

```powershell
python scripts/run_skill.py run --system-dir <cache-dir> --mission-id <id> --goal "核实条件后决定是否实验"
python scripts/run_skill.py context --system-dir <cache-dir> --mission-id <id>
python scripts/run_skill.py act --system-dir <cache-dir> --mission-id <id> --decision-file <decision.json>
python scripts/run_skill.py resume --system-dir <cache-dir> --mission-id <id> --summary "查询结论及限制" --evidence "<actual source>"
python scripts/run_skill.py resume --system-dir <cache-dir> --mission-id <id> --agent-completed
python scripts/run_skill.py reconcile --system-dir <cache-dir> --mission-id <id> --outcome unknown --summary "未能在设备端找到任务回执" --evidence "device-monitor:404"
```

Use `resume --answer` only after an actual user answer; use `--confirm --answer` or `--reject --answer` for a real approval or rejection. The selected Skill implementation is snapshot-bound; changes in its registry or source cause replanning rather than inheriting old approval.

## Compatibility

All mission execution uses Agent mode. Workflow nodes remain reference metadata for dependency hints and inspection; they are never used as an execution scheduler.
