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

## Cache-first execution

When the workflow library has already been imported, the Agent resolves and reuses its valid cache before starting a new task. It imports again only when no matching cache exists or when you explicitly ask to refresh, update, or reimport the workflow library. A spreadsheet, sample description, or other task input does not by itself rebuild the workflow-library cache.

For maintenance or troubleshooting, resolve an existing cache with:

```powershell
python scripts/labontology.py resolve-cache --skill-root ..\FduSkills --workspace .. --suite-id suite:fdu
```

## Install

Run these commands from this directory before using the Skill:

```powershell
python -m pip install -r requirements.txt
```

This installs the required `PyYAML` dependency in the Python environment that will run the commands below.

## FDU read-only example

Run these commands from this directory:

```powershell
python scripts/labontology.py import ..\FduSkills --suite-id suite:fdu --workspace ..
python scripts/labontology.py inspect --cache-dir ..\labontology_fdu_skill_cache
python scripts/labontology.py run --cache-dir ..\labontology_fdu_skill_cache --goal "检查实验步骤所需资源是否齐全"
python scripts/labontology.py status --cache-dir ..\labontology_fdu_skill_cache --mission-id <returned-mission-id>
```

`import` returns the cache directory and confirms that its graph is valid. `inspect` reports the suite, available Skills and capabilities, graph size, and whether every indexed source path still exists. `run` returns a new `mission_id` and the Runtime context; it does not execute a laboratory action by itself. `status` reads the mission record persisted beneath `<cache-dir>/runs`.

## Routine read-only actions

After an Agent has reviewed the `run` context and selected an eligible process Skill, use:

```powershell
python scripts/labontology.py decide --cache-dir <cache-dir> --mission-id <mission-id> --skill-id <skill-id> --reason "已核实该只读检查的目的"
```

The command prints the Skill, impact, and reason, then requires a `y` or `yes` confirmation. It only accepts runnable, read-only process Skills with no required input artifacts or device capabilities. It also verifies the selected Skill's recorded `SKILL.md` hash before delegating the decision to Runtime.

Device-facing or significant actions, missing inputs, missing evidence, unavailable instruction sources, and any request that needs scoped authorization stay in the internal Runtime approval path. Use `python scripts/runtime.py` for advanced `resume`, `reconcile`, and Agent-directed Runtime operations.
