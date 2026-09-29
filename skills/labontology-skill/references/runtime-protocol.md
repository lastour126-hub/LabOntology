# LabOntology Runtime Protocol

This reference describes how LabOntology plans, executes, resumes, and reports a laboratory task. The Skill document is the execution contract; Runtime records the current `SkillExecution` directly.

## Execution lifecycle

All document-based and script-assisted Skills use the same host-facing lifecycle. A script is optional and never creates a second execution path:

```text
prepare-skill → act → waiting_agent → host follows SKILL.md
                                      └─ optional script, if explicitly selected → resume → context
                                      └─ human decision → resume → context
                                      └─ interrupted action → reconcile → context
```

`act` does not automatically run a subprocess. It records one Skill action and returns `waiting_agent`; the host follows the prepared document and may explicitly use the listed optional script. The host reports the actual result and artifacts through `resume`.

When `execution_cycle.requires_resume` is `true`, inspect `execution_cycle.resume_mode` and finish exactly that pending branch before reading `context` again.

The context response separates `candidate_count` from `registered_skill_count` and includes `coverage_diagnostic`:

- `no_registered_skill`: no Skill was registered in the active workflow library;
- `candidate_review`: Skills are registered, but keyword matching did not prove which one applies; read the returned candidate documents;
- `candidate_found`: at least one Skill was ranked by the task description.

Neither a low match score nor a missing optional script proves that a Skill is unavailable. Always read the complete `SKILL.md` before deciding. A candidate whose input artifact is already present may also be surfaced even when its text score is zero. If no candidate covers the goal after document review, ask one focused clarification instead of inventing a capability.

`historical_experiences` is an optional, bounded advisory list containing at most three compact records from completed missions. Use it to recall practical constraints or useful output patterns, but never treat it as a capability match, input, approval, evidence, or completion proof. It does not replace reading the selected Skill document and does not modify the graph.

## Runtime state

Carry these values through the current task:

- `cache_dir`: the active workspace graph returned by `bootstrap`;
- `mission_id`: the current task record returned by `run`;
- `skill_id`: the selected Skill returned by `context`;
- `action_id`: the action ticket returned by `act`.

Never invent any of these values. Use the value returned by the previous Runtime command.

## Required sequence

Run commands from the LabOntology Skill directory. Keep command output internal and pass only the experiment result or the one necessary user question to the user.

### 1. Prepare or refresh the workspace

```powershell
python scripts/labontology.py bootstrap
```

The command creates the first workspace graph, reuses a current graph, or synchronizes changed Skills. Keep its returned `cache_dir`. A failed bootstrap stops the task; do not select a Skill.

### 2. Create or continue a mission

For a new user goal, create a mission with the exact natural-language goal. Attach files as mission inputs; they remain in place and are not graph files:

```powershell
python scripts/labontology.py run --cache-dir <cache-dir> --goal "<user goal>"
# Optional, repeat for each input file:
python scripts/labontology.py run --cache-dir <cache-dir> --goal "<user goal>" --input-artifact <artifact-id>=<path>
```

命令必须从 LabOntology Skill 根目录执行；如果宿主当前目录不同，先确认该目录下的脚本存在并使用其绝对路径。

For a follow-up to an existing task, keep its `mission_id` and read the current context:

```powershell
python scripts/labontology.py context --cache-dir <cache-dir> --mission-id <mission-id>
```

Every laboratory follow-up must cross this boundary before the host answers. This includes explaining, sorting, summarizing, reformatting, or locating a result from the previous turn. Run `bootstrap` again when required by the host workflow, then read the original mission with `context`; do not answer from conversation memory alone.

Read the returned mission state and candidate Skill cards. Select only one Skill from `skills`. Judge coverage from the candidate card, manifest, declared outputs, optional entrypoint metadata, and complete Skill document together. An optional script is an accelerator, not the Skill contract. If `missing_inputs` is non-empty, report the missing condition instead of claiming that the task is covered. If the goal has multiple operations, confirm that the selected Skill covers the current operation; use another context cycle for the next operation.

If `status` is `candidate_review`, the Runtime has not proved a match by keywords but has intentionally exposed candidates for document review. Do not report that the ability is missing before reading them. If the reviewed candidates do not cover the goal, ask one focused clarification. For an explicitly approved routine, read-only task only, use the documented `agent_fallback` branch.

### 3. Prepare one Skill document

After selecting a candidate, read and prepare its complete Skill document:

```powershell
python scripts/labontology.py prepare-skill --cache-dir <cache-dir> --mission-id <mission-id> --skill-id <skill-id>
```

Use the returned document as the current instructions. Do not replace this step with reading a script, README, MCP description, or implementation file. If the document changed or is unavailable, refresh the graph and reassess the task.

### 4. Issue one action

Create one decision file for the current Runtime decision. A Skill action uses:

```json
{
  "kind": "skill",
  "skill_id": "<skill-id>",
  "reason": "<why this Skill resolves the current task state>",
  "assessment": {
    "impact": "routine",
    "rationale": "<evidence-based reason>",
    "uncertainties": [],
    "authenticity_gaps": []
  }
}
```

Submit it only after `prepare-skill`:

```powershell
python scripts/labontology.py act --cache-dir <cache-dir> --mission-id <mission-id> --decision-file <decision-file>
```

Read the returned `execution_cycle` and mission status. A selected Skill normally waits for the host Agent result; it may also be blocked or waiting for a user decision. Do not invent missing inputs.

The host may use these other decisions when appropriate:

```json
{
  "kind": "request_human",
  "reason": "需要用户确认或补充事实",
  "question": "请确认样品编号和处理顺序。"
}
```

```json
{
  "kind": "complete",
  "reason": "结果和产物已经由 Runtime 记录，任务可以结束。"
}
```

`request_human` waits for the user; the answer returns to planning and sets `replan_required`. `complete` is valid only when Runtime has a successful `SkillExecution`, no untracked output, and no pending replan.

For an explicitly approved routine, read-only fallback, use:

```json
{
  "kind": "agent_fallback",
  "side_effect_level": "read_only",
  "reason": "用户已明确允许 Agent 直接完成只读分析",
  "assessment": {
    "impact": "routine",
    "rationale": "仅读取公开数据并计算指标",
    "uncertainties": [],
    "authenticity_gaps": [],
    "authorization": "用户明确同意 Agent 直接执行"
  }
}
```

Runtime records this result as `agent_native`. It does not run a subprocess automatically, and the result must not be described as a standard Skill result.

### 5. Continue the pending action

If `execution_cycle.requires_reconcile` is `true`, the action may have started before the host stopped. Reconcile it from external evidence before choosing another action:

```powershell
python scripts/labontology.py reconcile --cache-dir <cache-dir> --mission-id <mission-id> --outcome <not_started|succeeded|failed|unknown> --summary "<evidence-based result>"
```

Inspect `execution_cycle.resume_mode`. For `external_skill`, follow the prepared `SKILL.md`, optionally invoke its declared script accelerator, and report one bounded result with `action_id`. For `human_decision`, obtain the requested user reply and resume it:

```powershell
python scripts/labontology.py resume --cache-dir <cache-dir> --mission-id <mission-id> --answer "<actual user reply>"
```

Use `--confirm --answer "<actual approval>"` or `--reject --answer "<actual rejection>"` when the pending action asks for approval. Do not start another action, retry silently, or declare completion while the action is waiting.

### 6. Return the result to LabOntology

For a Skill result or approved Agent fallback, report the actual result, failure, evidence, and output artifacts:

```powershell
python scripts/labontology.py resume --cache-dir <cache-dir> --mission-id <mission-id> --action-id <action-id> --agent-completed --summary "<actual result>"
```

Use `--agent-failed` for a failed Skill action and include the explanation. Include `--provide-artifact <artifact-id>=<path>` when the Skill produced an output. An optional script result still uses this same `resume` path.

### 7. Continue or finish

After `act` or `resume`, read `context` again. If the mission is awaiting another decision, choose only one next action. If it is complete or blocked, report that state and one useful next step. Do not create a second action while the previous one is pending.

Runtime stores plans, protocol files, submission records, and other outputs under the mission artifact directory returned as `artifact_dir`. Do not place task inputs or outputs in the graph cache; return external outputs through `resume --provide-artifact` or `reconcile --provide-artifact`.

## Workflow maintenance

Self-evolution is a reviewed graph-maintenance path, not an automatic rewrite after one failure:

```powershell
python scripts/labontology.py suggest-maintenance --cache-dir <cache-dir>
python scripts/labontology.py maintain-graph --cache-dir <cache-dir> --patch-file <patch-file> --reason "<reviewed reason>"
python scripts/labontology.py restore-backup --cache-dir <cache-dir>
```

`maintain-graph` applies only a validated low-risk patch and keeps one latest backup. Do not modify Skill documents, device commands, parameters, approvals, or mission history through graph maintenance.

## Failure handling

- Bootstrap failure: stop and report that the workflow library is unavailable.
- No registered Skill: report that the relevant ability is not installed or initialized.
- Candidate review: read the returned Skill documents before deciding that no ability applies.
- Missing input or capability: report the missing condition; do not fabricate it.
- Skill document changed: refresh the graph and run `prepare-skill` again.
- Skill or optional script failure: resume the failure with evidence; do not silently retry. Read `context` and replan.
- Interrupted action: reconcile from external evidence before considering another action.
- User correction or repeated failure: return to LabOntology workflow maintenance; do not edit Skill documents or mission history automatically.
