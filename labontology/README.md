# LabOntology Quick Start

`labontology` is one self-contained Skill with two internal modules:

- Creator discovers a Skill directory and maintains its graph cache.
- Runtime owns mission state, evidence, execution, recovery, and approvals.

The public entrypoint keeps those boundaries intact while providing a short path for normal use. It does not import external historical Skills.

## Use it in conversation

Tell an Agent what you need to accomplish in ordinary laboratory language. For example:

- "I am preparing a sample treatment experiment. What should I check first?"
- "Before starting, are the materials and equipment for this procedure ready?"
- "I paused this experiment yesterday. What is the current status and next step?"

The Agent selects the workflow internally, checks the available procedures and task state, and asks only for missing information. It explains what is ready, what needs attention, and what can happen next. It does not start device actions without the required approval.

Responses are written for experiment users rather than developers: the result comes first, followed by the next action or the one missing condition. Technical terms such as cache paths and Suite IDs appear only when maintaining or troubleshooting the workflow library.

Typical conversations:

- “准备条件已检查完成；目前只缺少离心机可用性确认。”
- “我找到昨天暂停的任务，已保留已有结果。是否继续下一步？”
- “这是只读检查，不会改变设备状态。确认后我再执行。”
- “实验流程库需要更新；我会只同步这次任务相关的步骤。”

## Unified workspace graph

Each laboratory workspace has one cache named `labontology_workspace_cache`. It stores one graph containing all explicit `SkillSuite` collections and their general Skills. The Agent synchronizes the workspace before planning: new or changed Skill sources update this same graph, while a spreadsheet, sample description, or other task input becomes a mission input and never rebuilds the workflow-library cache.

For maintenance or troubleshooting, resolve an existing cache with:

```powershell
python scripts/labontology.py sync --skill-root ..\FduSkills --workspace .. --suite-id suite:fdu
python scripts/labontology.py resolve-cache --skill-root ..\FduSkills --workspace .. --suite-id suite:fdu
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
python scripts/labontology.py sync --skill-root ..\FduSkills --suite-id suite:fdu --workspace ..
python scripts/labontology.py inspect --cache-dir ..\labontology_workspace_cache
python scripts/labontology.py run --cache-dir ..\labontology_workspace_cache --suite-id suite:fdu --goal "检查实验步骤所需资源是否齐全"
python scripts/labontology.py status --cache-dir ..\labontology_workspace_cache --mission-id <returned-mission-id>
```

`sync` returns the workspace cache and confirms that its graph is valid. `inspect` reports every Suite, available capabilities, graph size, and source freshness. `run` returns a new `mission_id` and the Runtime context; it does not execute a laboratory action by itself. Add `--input-artifact <name>=<path>` to attach a task spreadsheet or other task input. `status` and `resume` read or continue the mission record persisted beneath `<cache-dir>/runs`.

## Routine read-only actions

After an Agent has reviewed the `run` context and selected an eligible process Skill, use:

```powershell
python scripts/labontology.py decide --cache-dir <cache-dir> --mission-id <mission-id> --skill-id <skill-id> --reason "已核实该只读检查的目的"
```

The command prints the Skill, impact, and reason, then requires a `y` or `yes` confirmation. It only accepts runnable, read-only process Skills with no required input artifacts or device capabilities. It also verifies the selected Skill's recorded `SKILL.md` hash before delegating the decision to Runtime.

Device-facing or significant actions, missing inputs, missing evidence, unavailable instruction sources, and any request that needs scoped authorization stay in the internal Runtime approval path. Use `python scripts/runtime.py` for advanced `resume`, `reconcile`, and Agent-directed Runtime operations.
