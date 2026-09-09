# Agent Runtime protocol

The host Agent reasons about the goal, chooses Skills, reads observations and replans. Python executes one selected action at a time; it does not embed model inference. Knowledge, analysis and device Skills share a registry. No workflow or artifact-producing goal is required.

## Context and storage

Canonical cache data stays read-only: `ontology.jsonl` is the only normalized graph and `source-index.json` points to external package files by path and hash. Context combines runtime contracts with descriptions, evidence and unresolved fields from the graph. All Skills, including pure Agent and zero-output Skills, remain candidates. Workflow references are optional graph substructures.

Agent mode includes all suites in the selected registry by default. `--suite ID` narrows selection. If different suites reuse a Skill ID, select a suite explicitly to avoid ambiguous execution. This does not scan other cache directories or install unregistered Skills.

`<cache>/runs/<mission>/state.json` stores goal, constraints, decisions, observations, artifacts, pending_action, skill_executions and status. `events.jsonl` timestamps transitions. Each invocation gets a distinct `action:N` ID, even when repeating a Skill. Temporary acquired knowledge belongs in observations/runs; persistent canonical updates belong to Creator.

## Host Agent loop

1. `run --system-dir CACHE --mission-id ID --goal GOAL [--constraint TEXT] [--input-artifact ID=PATH]` initializes Agent mode and returns context. Repeating run loads existing state, without restarting actions. A new goal needs a new mission ID.
2. Read the selected Skill instructions and relevant knowledge. Assess evidence, current gaps, capability availability, actual impact and existing authorization.
3. Write one decision JSON, then call `act --system-dir CACHE --mission-id ID --decision-file PATH`.
4. Inspect returned context. `awaiting_decision` means continue reasoning; `waiting_agent` means execute the chosen Agent Skill and report completion. Do not ask the user to orchestrate routine steps.
5. `waiting_human` means actually ask the recorded question and wait for a real reply. Reassess after factual clarification; scoped approval can resume the specific high-impact action.
6. Complete only when evidence supports the user's success conditions.

## Decision JSON

Choose one Skill:

```json
{
  "kind": "skill",
  "skill_id": "literature-experiment-recommender",
  "reason": "Find evidence before selecting device operations",
  "assessment": {
    "impact": "routine",
    "rationale": "Read literature; no experimental operation is being submitted",
    "uncertainties": [],
    "authenticity_gaps": []
  }
}
```

Optional `inputs` maps artifact IDs to existing local paths. Required inputs and available capabilities are checked for both process and Agent Skills. Report actually established capabilities using `--capability ID`; do not invent them to bypass a block.

### Skill document review

When context for a process Skill contains `instruction_source`, read that current `SKILL.md` before choosing it. Add a receipt to the decision using the exact path and SHA-256 supplied by context:

```json
"reviewed_instruction": {
  "path": "C:/lab-skills/example/SKILL.md",
  "sha256": "<current hash from instruction_source>"
}
```

Runtime checks that the document still exists and its hash still matches the cache before it accepts the action. A changed document requires a Creator refresh and a new assessment. This proves that the instructions were reviewed at the current revision; it does not replace the Agent's responsibility to follow them. Agent-mode Skills do not require a review receipt.

To explicitly retry an eligible failed read-only process action, add `retry_of` to a normal Skill decision. The target must be the same Skill, have status `failed` or `timed_out`, be marked retryable, be read-only, and remain below its declared retry limit. Runtime rejects every other retry request and never generates a retry decision itself.

Capability declarations persist within the mission across CLI commands. The Agent must still recheck actual availability before an operation if conditions change; a recorded capability is not a live device-health probe.

Assessment concerns the chosen action, not every unknown about the final experiment. A knowledge query can be routine while experimental conditions remain unknown. `uncertainties` and `authenticity_gaps` describe material issues that require human judgment for the chosen action. `impact: significant` describes major consequences. Optional `authorization` quotes or identifies the user's existing authorization for this exact scope; it is a record, not a self-granted permission.

Missing prerequisites or explicit blocking policies produce a blocked observation and return to reasoning. Significant impact without existing scoped authorization, material uncertainty/authenticity gaps or an explicit confirmation policy produces `waiting_human`. Cached unresolved fields are not automatic approval gates.

Ask for a fact or decision:

```json
{
  "kind": "request_human",
  "reason": "Available sources cannot establish the physical sample identity",
  "question": "Which sample is loaded, and what record identifies it?"
}
```

Complete without requiring a file:

```json
{
  "kind": "complete",
  "reason": "Verified sources answer the question; no device experiment is needed"
}
```

Every decision needs a concrete reason. A pending action cannot be overwritten. Only registered Skill IDs are accepted; decision JSON cannot supply executable commands.

## Completion and replies

All commands below also require `--system-dir CACHE --mission-id ID`.

| Event | Command |
|---|---|
| Textual result | `resume --summary "Result and limitations" --evidence "Actual source"` |
| No-output completion | `resume --agent-completed` |
| Agent Skill failed | `resume --agent-failed --summary "Failure reason"` (optional evidence, no required outputs) |
| Declared file output | `resume --provide-artifact artifact:report=PATH` (repeat as needed) |
| Actual answer to standalone question | `resume --answer "User reply"` |
| Factual clarification for pending action | `resume --answer "Actual clarifying reply"` (returns to reasoning) |
| Exact high-impact action approved | `resume --confirm --answer "Actual approval and scope"` |
| Rejected action | `resume --reject --answer "Actual rejection or revised constraint"` |

Without a completion signal, resume leaves an Agent Skill pending. A summary or completion flag suffices for an empty output contract. Declared output paths must exist. No dummy file is needed for a Skill without outputs. Approval alone does not prove facts: uncertainty/authenticity clarification is recorded and returned to the Agent for reassessment. Approval does not carry forward to another action.

Confirmation/rejection requires a nonempty record of the actual user reply. Runtime cannot authenticate a claimed reply or source; the host Agent must never fabricate either. Agent failure must be reported with `--agent-failed`, otherwise a summary is interpreted as completion.

Pending decisions retain the selected suite/registry and contract snapshot. If the selected Skill changes before approval/execution or Agent completion, Runtime returns to reasoning instead of treating the old decision as permission for a different implementation. CLI JSON is UTF-8, including Chinese goals and observations.

## Failure and interruption

Process failure, timeout or missing output becomes an observation. Never blindly retry a side effect. Inspect logs and decide whether to query status, gather evidence, change Skills or ask a human. State is persisted as `running` before invoking. If execution is interrupted, commands deliberately leave it pending rather than guess whether it ran; inspect actual device/process status and reconcile before further operations.

Use `reconcile --outcome {not_started,succeeded,failed,unknown} --summary TEXT --evidence VALUE` to record the external result without rerunning the Skill. A reconciled success requires every declared output through repeatable `--provide-artifact ID=PATH`; other outcomes reject provided outputs. Reconciliation persists a dedicated event and returns the mission to Agent reasoning. It does not execute a subprocess, repeat a device request or manufacture evidence.

Python validates process exit and output existence, not scientific correctness. The host Agent must inspect actual results and sources. Context includes bounded stdout/stderr excerpts and run-directory paths for deeper inspection.

## Compatibility

All mission execution uses Agent mode. Workflows are reference metadata only and can inform decisions without being executed.
