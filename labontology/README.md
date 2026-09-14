# LabOntology Quick Start

`labontology` is one self-contained Skill with two internal modules:

- Creator discovers a Skill directory and maintains its graph cache.
- Runtime owns mission state, evidence, execution, recovery, and approvals.

The public entrypoint keeps those boundaries intact while providing a short path for normal use. It does not import external historical Skills.

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
