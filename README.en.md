<p align="center">
  <img src="assets/labontology-banner.svg" alt="LabOntology: keep experimental steps, evidence, and results connected" width="100%">
</p>

<h2 align="center">Keep experimental steps, evidence, and results connected, so you can pick up where you left off.</h2>

<p align="center">
  <a href="#what-it-does">What it does</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="Examples.en.md">Examples</a> ·
  <a href="#repository-layout">Repository layout</a>
</p>

<p align="center"><a href="README.md">中文</a> · English</p>

An experimental task only needs to specify its goal, available materials, and constraints. LabOntology organizes the capabilities needed for the task, arranges the experimental steps, and checks each step's inputs, outputs, and conditions. When materials are missing, results look abnormal, or conditions change, completed work is preserved, the task is paused, and the remaining steps are adjusted. The task can continue across long or later conversations without reconstructing the whole workflow.

## What it does

- Before starting, it checks experimental conditions and available Skills, then tells you what is missing.
- As work proceeds, it keeps steps in the agreed order and records the evidence and results.
- If something goes wrong, it keeps completed work and adjusts what comes next.
- When you return, it reads the task record and reminds you of conditions that were missed before.

### How a task works

Tell LabOntology what you want to do. It checks whether the current experimental setup can handle the task and what is missing. It moves through feasible steps in order and records each result. If it cannot proceed, it stops and explains why. Once the missing conditions are met, or when you return later, it reads the existing record and picks up where it left off.

## Quick start

Install LabOntology first, then install the experimental Skills needed for your task. Python 3.11 or newer is required. The experimental Skills used in the examples are obtained through [SCPHub](https://scphub.intern-ai.org.cn/). The [examples](Examples.en.md) page shows six complete cases and their installation prompts.

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

The six independent cases cover small-molecule analysis, lead screening, ELISA data analysis, physics simulation, synthetic-biology simulation, and crystal-structure analysis. All required data is included in the prompts or generated from stated parameters. Each case includes SCPHub Skill installation prompts, task prompts, and completion requirements. [See the examples](Examples.en.md).

## Scope and limits

LabOntology organizes tasks and records their state. The corresponding experimental Skills carry out the specific work; LabOntology does not directly control instruments. If materials, conditions, or a suitable Skill are missing, it explains why the task cannot proceed. Instrument-related or other high-impact actions are not run automatically.

## Repository layout

- [SKILL.md](skills/labontology-skill/SKILL.md): the entry point and usage boundaries for experimental tasks.
- [references/](skills/labontology-skill/references/): ontology definitions and the [runtime protocol](skills/labontology-skill/references/runtime-protocol.md).
- [scripts/](skills/labontology-skill/scripts/): workflow-library preparation, task state, and result recording.
