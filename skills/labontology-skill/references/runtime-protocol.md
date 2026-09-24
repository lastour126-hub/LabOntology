# LabOntology Runtime Protocol

This reference is for the LabOntology supervisor when a laboratory task must be planned, executed, resumed, or reported. It is not a user-facing installation guide.

## One Worker lifecycle

All Workers use the same host-facing lifecycle. The document is the canonical contract; an optional script never creates a second Runtime path:

```text
prepare-skill → act → waiting_agent → host follows SKILL.md
                                      └─ optional script, if explicitly selected → resume → context
                                      └─ human decision → resume → context
                                      └─ legacy interrupted task → reconcile → context
```

`act` does not execute a subprocess. It records one document Worker ticket and returns `waiting_agent`; the host follows the prepared document and may explicitly use the listed optional script. The host reports the actual result and artifacts through `resume`.

When `worker_cycle.requires_resume` is `true`, inspect `worker_cycle.resume_mode` and complete exactly that pending branch before reading `context` again.

The context response separates `candidate_count` from `registered_skill_count` and includes `coverage_diagnostic`. Use only the returned `skills` when `match_found` is `true`; `match_found: false` means that no Worker is sufficiently matched and requires one focused clarification. Before asking, report `coverage_diagnostic.user_message` so the user knows that the task has not started and whether the environment has no registered Worker (`no_registered_worker`) or has registered Workers but no sufficiently matched candidate (`no_matching_worker`). Do not describe either condition as an execution failure. A Worker whose declared input artifact is already present may also be surfaced even when its text match score is zero; inspect its description before selecting it. The presence or absence of an optional script never excludes a document Worker.

`historical_experiences` is an optional, bounded advisory list containing at most three compact records from previously completed missions. Use it to recall practical constraints or useful output patterns, but never treat it as a Worker match, input, capability, approval, evidence, or completion proof. It does not replace reading the selected Skill document and does not modify the graph.

## Runtime state

Carry these values through the current task:

- `cache_dir`: the active workspace graph returned by `bootstrap`;
- `mission_id`: the current task record returned by `run`;
- `skill_id`: the selected Worker Skill returned by `context`;
- `action_id`: the one action ticket returned by `act`.

Never invent any of these values. Use the value returned by the previous Runtime command.

## Required sequence

Run commands from the LabOntology Skill directory. Keep command output internal and pass only the experiment result or the one necessary user question to the user.

### 1. Prepare or refresh the workspace

```powershell
python scripts/labontology.py bootstrap
```

The command creates the first workspace graph, reuses a current graph, or synchronizes changed Worker Skills. Keep its returned `cache_dir`. A failed bootstrap stops the task; do not call a Worker.

### 2. Create or continue a mission

For a new user goal, create a mission with the exact natural-language goal. Attach files as mission inputs; they remain in place and are not graph files:

```powershell
python scripts/labontology.py run --cache-dir <cache-dir> --goal "<user goal>"
# Optional, repeat for each input file:
python scripts/labontology.py run --cache-dir <cache-dir> --goal "<user goal>" --input-artifact <artifact-id>=<path>
```

上述命令必须从 LabOntology Skill 根目录执行；如果宿主当前目录不同，先确认该目录下的脚本存在并将 `scripts/labontology.py` 替换为其绝对路径。不要假设宿主当前目录天然包含 `scripts/`。

For a follow-up to an existing task, keep its `mission_id` and use `context` instead of creating a second mission for the same goal:

```powershell
python scripts/labontology.py context --cache-dir <cache-dir> --mission-id <mission-id>
```

Every laboratory follow-up must cross this boundary before the host answers. This includes a request to explain, sort, summarize, reformat, or locate a result from the previous turn. Even when no new Worker action is needed, run `bootstrap` (a hot-start `reused=true` result is valid) and then read the original mission with `context`; do not answer from conversation memory alone. If the mission is complete, `context` is the read-only proof that the recorded artifact can be reported. If the follow-up changes the goal or requests another operation, use the returned state to replan before selecting a Worker or issuing `complete`.

Read the returned mission state and candidate Worker cards. Select only one candidate from `skills` and only when `match_found` is `true`. Judge coverage from the candidate card, manifest, declared outputs, optional entrypoint metadata, and complete Skill document together; an optional script is evidence and an accelerator, not the Worker contract. Still read the complete `SKILL.md` before acting. The selected Worker's declared inputs, outputs, description, and prepared Skill document must cover the current goal; an input-artifact match alone is not enough. If `missing_inputs` is non-empty, or the combined contract and Skill document cover only one part of a multi-operation goal, do not issue a `kind=skill` action; report the missing condition or missing Worker instead of claiming that the whole goal is covered. If there is no match, report `coverage_diagnostic.user_message`; when `fallback_available` is true, offer `fallback_message` and wait for explicit user approval before considering `agent_fallback`. The fallback is limited to routine, read-only work and must be recorded as `agent_native`; it is not a Worker result. If an input, capability, or Worker is unavailable, report that missing condition. If the mission is waiting for a human or external result, follow the corresponding resume branch instead of issuing another action. After a human answer, `replan_required` is true: read `context` again, reassess the goal, and choose a Worker, issue an approved `agent_fallback`, or ask the next focused clarification; do not issue `complete` or perform the work outside a Worker or approved fallback. Do not choose from `registered_skill_count` or treat script presence as a Worker eligibility test.

### 3. Prepare exactly one Worker

After selecting a candidate, read and prepare its complete Skill document:

```powershell
python scripts/labontology.py prepare-skill --cache-dir <cache-dir> --mission-id <mission-id> --skill-id <skill-id>
```

Use the returned document as the current Worker instructions. Do not replace this step with reading a script, README, or implementation file. If the document changed or is unavailable, refresh the graph and reassess the task.

### 4. Issue one Worker action

Create one decision file for the current Runtime decision. A Worker action uses:

```json
{
  "kind": "skill",
  "skill_id": "<skill-id>",
  "reason": "<why this one Worker resolves the current task state>",
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

Read the returned `worker_cycle` and mission status. A selected Worker normally waits for the host Agent result; it may also be blocked or waiting for a user decision. Do not invent missing inputs.

The host Agent may use these non-Worker decisions when appropriate:

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

`request_human` waits for the user; its answer returns to planning and sets `replan_required`. `complete` is valid only when Runtime has no untracked output and the mission is not waiting for that replan. Neither branch may bypass safety, approval, input, or Worker read gates.

For an explicitly approved low-risk read-only fallback, use:

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

Runtime waits for the host Agent and records the result source as `agent_native`. It does not run a subprocess automatically, and the result must not be described as a standard Worker result.

### 5. Continue the returned Worker state

If `worker_cycle.requires_reconcile` is `true`, the action may have started before the host stopped. Use external evidence and reconcile it before choosing another Worker:

```powershell
python scripts/labontology.py reconcile --cache-dir <cache-dir> --mission-id <mission-id> --outcome <not_started|succeeded|failed|unknown> --summary "<evidence-based result>"
```

Inspect `worker_cycle.resume_mode`. For `external_worker`, follow the prepared `SKILL.md`, optionally invoke its declared script accelerator, and report exactly one bounded result with `action_id`; for `human_decision`, obtain the requested user reply and resume it as a human answer or approval:

```powershell
python scripts/labontology.py resume --cache-dir <cache-dir> --mission-id <mission-id> --answer "<actual user reply>"
```

Use `--confirm --answer "<actual approval>"` or `--reject --answer "<actual rejection>"` when the pending action asks for approval. Do not call another Worker, retry silently, or declare completion while the action is waiting.

### 6. Return only waiting results to LabOntology

For an external Worker result or an approved Agent fallback, report the actual result, failure, evidence, and output artifacts with the action ticket:

```powershell
python scripts/labontology.py resume --cache-dir <cache-dir> --mission-id <mission-id> --action-id <action-id> --agent-completed --summary "<actual result>"
```

Use `--agent-failed` for a failed document Worker action and include its explanation. Include `--provide-artifact <artifact-id>=<path>` when the Worker produced an output. An optional script result is still reported through this same `resume` path.

### 7. Continue or finish

After `act` or `resume`, read `context` again. If the mission is awaiting another decision, choose only one next action. If it is complete or blocked, report that state and one useful next step. Do not create a second Worker action while the previous action is still pending.

Runtime stores generated plans, protocol files, submission records, and other outputs under the mission artifact directory returned as `artifact_dir`. Do not place task inputs or outputs in the graph cache; return external outputs through `resume --provide-artifact` or `reconcile --provide-artifact`.

## Workflow maintenance

Self-evolution is a reviewed graph-maintenance path, not an automatic rewrite after one failure:

```powershell
python scripts/labontology.py suggest-maintenance --cache-dir <cache-dir>
python scripts/labontology.py maintain-graph --cache-dir <cache-dir> --patch-file <patch-file> --reason "<reviewed reason>"
python scripts/labontology.py restore-backup --cache-dir <cache-dir>
```

`maintain-graph` applies only the validated low-risk patch and keeps one latest backup. Do not modify Worker Skill documents, device commands, parameters, approvals, or mission history through graph maintenance.

## Failure handling

- Bootstrap failure: stop and report that the workflow library is unavailable.
- No matching candidate: first report `coverage_diagnostic.user_message`; if the task is routine and read-only, offer `fallback_message` and wait for explicit approval before using `agent_fallback`.
- Missing input or capability: report the missing condition; do not fabricate it.
- Worker document changed: refresh the graph and run `prepare-skill` again.
- Worker or optional script failure: resume the failure with evidence; do not silently retry. Read `context` and replan.
- Interrupted action: reconcile from external evidence before considering another action.
- User correction or repeated failure: return to LabOntology workflow maintenance; do not edit Worker Skills or mission history automatically.
