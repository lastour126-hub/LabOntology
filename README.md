<p align="center">
  <img src="assets/labontology-banner.svg" alt="LabOntology" width="100%">
</p>

<p align="center">
  <a href="#overview">Overview</a> ·
  <a href="#execution-architecture-for-autonomous-experiments">Execution architecture</a> ·
  <a href="#organizing-and-advancing-experimental-tasks">Workflow</a> ·
  <a href="#schema-modeling">Schema</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="Examples.md">Examples</a> ·
  <a href="#repository-layout">Repository layout</a>
</p>

<p align="center">English · <a href="README.zh.md">中文</a></p>

<a id="overview"></a>

LabOntology is an agent Skill package for autonomous laboratory work. It helps agents organize experimental knowledge, workflow structure, execution constraints, equipment capabilities, and result data into a shared information network they can query and reason over to guide execution. Agents can use this network to plan tasks, match experimental capabilities, check execution conditions, and record each result with its supporting evidence. It supports the task lifecycle from planning and execution through monitoring and review.

## Execution architecture for autonomous experiments

Tasks contain workflows, and workflows consist of nodes. Nodes are linked to the experimental capabilities they require, and those capabilities are matched with equipment and runtime environments. Execution artifacts link back to the task, allowing agents to understand its structure and trace where results came from.

![Autonomous experiment execution architecture](assets/autonomous-experiment-architecture.png)

## Organizing and advancing experimental tasks

The workflow organizes experimental steps as nodes, with preconditions and checkpoints indicating when to proceed. After a node completes, the agent uses its state and results to decide what comes next. If information is missing or an issue arises, the plan can be adjusted or held for confirmation, while completed results remain in the task record.

![Experimental task workflow from goal to review and continuation](assets/autonomous-experiment-workflow.png)

## Schema modeling

The Schema has definition, data, control, and execution layers, which describe experimental objects, task records, execution rules, and runtime state. Relationships connect these layers, giving experimental knowledge and operations a consistent representation.

![LabOntology Schema entities and relationships](assets/schema-model.png)

## Quick start

Install LabOntology first, then install the experimental Skills needed for your task. Python 3.11 or newer is required. The experimental Skills used in the examples are obtained through [SCPHub](https://scphub.intern-ai.org.cn/). The [examples](Examples.md) page shows six complete cases and their installation prompts.

### Codex

Enter this in a Codex conversation:

```text
$skill-installer Install this Skill from https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill
```

For manual installation, place the Skill directory in `~/.agents/skills/labontology/` for all your projects, or in `.agents/skills/labontology/` for one project. See the [Codex Skills documentation](https://learn.chatgpt.com/docs/build-skills).

### Claude Code

Enter this in Claude Code:

```text
Install https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill into ~/.claude/skills/labontology/. Retrieve only this Skill directory.
```

To use it in just one project, change the destination to that project's `.claude/skills/labontology/`. See the [Claude Code Skills documentation](https://code.claude.com/docs/en/skills).

### Other agents

[Cursor](https://prod.cursor.com/help/customization/skills), [Gemini CLI](https://geminicli.com/docs/cli/skills/), and [OpenCode](https://opencode.ai/docs/skills) can discover Skills from `.agents/skills/`. Enter this in the agent you use:

```text
Install https://github.com/lastour126-hub/LabOntology/tree/master/skills/labontology-skill into ~/.agents/skills/labontology/. Retrieve only this Skill directory.
```

For a single project, use `.agents/skills/labontology/` within that project instead. Check for an existing directory with the same name before installing. Then start a new session or use your agent's skill reload command.

Install any experimental Skills in a directory your agent can discover, too. Once the environment is ready, you can ask it to “initialize LabOntology for this project” or simply start an experimental task. The first task initializes it automatically; you do not need to create it again in the same project.

## Examples

The six independent cases cover small-molecule analysis, lead screening, ELISA data analysis, physics simulation, synthetic-biology simulation, and crystal-structure analysis. All required data is included in the prompts or generated from stated parameters. Each case includes SCPHub Skill installation prompts, task prompts, and completion requirements. [See the examples](Examples.md).

## Scope and limits

LabOntology organizes tasks and records their state. The corresponding experimental Skills carry out the specific work; LabOntology does not directly control instruments. If materials, conditions, or a suitable Skill are missing, it explains why the task cannot proceed. Instrument-related or other high-impact actions are not run automatically.

## Repository layout

- [SKILL.md](skills/labontology-skill/SKILL.md): the entry point and usage boundaries for experimental tasks.
- [references/](skills/labontology-skill/references/): ontology definitions and the [runtime protocol](skills/labontology-skill/references/runtime-protocol.md).
- [scripts/](skills/labontology-skill/scripts/): workflow-library preparation, task state, and result recording.
