# LabOntology Quick Start

`labontology` is one self-contained Skill with two internal modules:

- Creator discovers visible standard Skill directories and maintains one workspace cache.
- Runtime owns mission state, evidence, execution, recovery, and approvals.

LabOntology is the entrypoint for laboratory work and workflow-library maintenance. Other laboratory Skills are worker capabilities selected by LabOntology; they are not direct user-request entrypoints. Ordinary writing, spreadsheet, image, presentation, and general file-generation tasks stay outside LabOntology unless they are part of a laboratory task. Feedback from repeated failures or corrections may be used to maintain the workflow graph within the existing safety boundary.

The public entrypoint keeps those boundaries intact while providing a short path for normal use. It does not import external historical Skills.

## Use it in conversation

Tell an Agent what you need to accomplish in ordinary laboratory language. For example:

- "I am preparing a sample treatment experiment. What should I check first?"
- "Before starting, are the materials and equipment for this procedure ready?"
- "I paused this experiment yesterday. What is the current status and next step?"

The Agent selects the workflow internally, checks the available procedures and task state, and asks only for missing information. It explains what is ready, what needs attention, and what can happen next. It does not start device actions without the required approval.

Responses are written for experiment users rather than developers: the result comes first, followed by the next action or the one missing condition. Technical terms such as cache paths and Suite IDs appear only when maintaining or troubleshooting the workflow library.

When you describe the experimental sequence in conversation, the Agent turns it into a short proposed flow and asks you to confirm the order. Confirmed steps are treated as workflow evidence; unrelated Skills in the same project are not automatically combined into one procedure.

Typical conversations:

- “准备条件已检查完成；目前只缺少离心机可用性确认。”
- “我找到昨天暂停的任务，已保留已有结果。是否继续下一步？”
- “这是只读检查，不会改变设备状态。确认后我再执行。”
- “实验流程库需要更新；我会只同步这次任务相关的步骤。”

## Normal installation and first use

Install LabOntology and the laboratory Worker Skills as ordinary `SKILL.md` directories in the host's normal Skill location. The user only needs to describe the laboratory goal in natural language.

On the first laboratory request, LabOntology discovers the visible standard Skill directories and creates the workspace cache automatically. Later requests reuse that cache; a changed, added, or removed Worker Skill triggers synchronization. The user does not need to call LabOntology by name or provide Skill paths.

Worker Skill source files are read-only inputs to LabOntology. LabOntology does not rewrite or add configuration to those Skills.

## Unified workspace graph

Each laboratory workspace has one cache named `labontology_workspace_cache`. It stores one graph containing all visible Worker Skills. The Agent prepares the workspace before planning: new or changed Skill sources update this same graph, while a spreadsheet, sample description, or other task input becomes a mission input and never rebuilds the workflow-library cache.

For maintainers who need to inspect automatic discovery explicitly:

```powershell
python scripts/labontology.py bootstrap
```

`bootstrap` uses the current workspace and visible Skill locations by default. When started from a project-local path such as `<project>/.claude/skills/labontology-skill`, it automatically uses `<project>` as the workspace. An explicit root is only an advanced maintenance or test override.

For maintenance or troubleshooting, resolve an existing cache with:

```powershell
python scripts/labontology.py sync --skill-root ..\..\..\FduSkills --workspace ..\..\.. --suite-id suite:fdu
python scripts/labontology.py resolve-cache --skill-root ..\..\..\FduSkills --workspace ..\..\.. --suite-id suite:fdu
```

## Install

发布包已内嵌固定版本的 PyYAML（6.0.3），正常使用不需要单独安装 PyYAML。开发环境仍可执行：

```powershell
python -m pip install -r requirements.txt
```

这会为开发和测试环境安装同版本 `PyYAML`；公开入口会优先使用 Skill 内置版本。

## FDU read-only example

Run these commands from this directory:

```powershell
python scripts/labontology.py sync --skill-root ..\..\..\FduSkills --suite-id suite:fdu --workspace ..\..\..
python scripts/labontology.py inspect --cache-dir ..\..\..\labontology_workspace_cache
python scripts/labontology.py run --cache-dir ..\..\..\labontology_workspace_cache --suite-id suite:fdu --goal "检查实验步骤所需资源是否齐全"
python scripts/labontology.py status --cache-dir ..\..\..\labontology_workspace_cache --mission-id <returned-mission-id>
```

`sync` returns the workspace cache and confirms that its graph is valid. `inspect` reports every Suite, available capabilities, graph size, and source freshness. `run` returns a new `mission_id` and the Runtime context; it does not execute a laboratory action by itself. Add `--input-artifact <name>=<path>` to attach a task spreadsheet or other task input. `status` and `resume` read or continue the mission record persisted beneath `<cache-dir>/runs`.

The model-facing Runtime protocol is maintained in [references/runtime-protocol.md](references/runtime-protocol.md). It defines the mission state, Worker read gate, one-action rule, result return, and failure handling. Keep this README focused on installation, maintenance, and troubleshooting.

Generated plans, protocol files, submission records, and other Agent outputs are stored under `<cache-dir>/runs/<mission-id>/artifacts`. Input files such as a spreadsheet are referenced in place and are not moved.

All Skill actions use the same `act` entrypoint. A decision may select one document Worker, request a human answer, use an explicitly approved low-risk read-only Agent fallback, or complete the mission after Runtime checks. Every selected Worker or fallback enters `waiting_agent`; the host Agent follows the prepared `SKILL.md` for a Worker, or performs the approved native analysis for a fallback, and returns the actual result through `resume`. Fallback results are recorded as `agent_native` and are not presented as standard Worker results. If that document declares an optional script accelerator, the host may invoke it explicitly after checking its inputs and outputs; LabOntology never auto-starts a local process merely because a script exists. After a human answer, `context` returns `replan_required=true`; the Agent must reassess and select a Worker, use an approved fallback, or ask the next focused clarification, and Runtime rejects direct completion. If `match_found` is false, the Agent reports the reason and offers the fallback only for routine read-only work. A Worker whose declared input artifact is already present may be surfaced even when keyword overlap is absent, so the Agent must inspect the returned Worker card before deciding. The Agent records the user's confirmation in the decision assessment before issuing the action; device-facing or significant actions, missing inputs, missing evidence, unavailable instruction sources, and scoped authorization remain in the Runtime approval path. Use `python scripts/runtime.py` for advanced `resume`, `reconcile`, and Agent-directed Runtime operations.

## Lightweight self-maintenance

Runtime feedback is stored as observable JSONL events, not hidden reasoning. After repeated missing conditions or failures, inspect suggestions without changing the graph:

```powershell
python scripts/labontology.py suggest-maintenance --cache-dir <cache-dir>
```

After explicit review, apply only a low-risk metadata or relationship patch:

```powershell
python scripts/labontology.py maintain-graph --cache-dir <cache-dir> --patch-file patch.json --reason "补充重复缺失的前置条件"
```

Graph replacement keeps a single latest backup in `<cache-dir>/.backup/`. There are no ontology versions; recovery is explicit:

```powershell
python scripts/labontology.py restore-backup --cache-dir <cache-dir>
```

Successful missions also leave a compact advisory record in
`<cache-dir>/experiences.jsonl`. The next `context` may return at most three
similar records as `historical_experiences`. These records are only hints for
the Agent: they never select a Worker, satisfy a missing input, bypass a
safety check, or modify the graph. Failed missions remain in `feedback.jsonl`.
