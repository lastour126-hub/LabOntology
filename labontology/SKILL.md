---
name: labontology
description: Use when importing a laboratory Skill suite, inspecting a validated LabOntology cache, or safely starting and reviewing a laboratory mission through one release-facing workflow.
---

# LabOntology

Use `python scripts/labontology.py` from this directory as the release-facing entrypoint.

## Commands

- `import`: discover a Skill directory, create a compact cache, and validate its graph.
- `inspect`: summarize the selected cache, its Skills, capabilities, graph, and source paths.
- `run`: create an Agent-mode mission and show the Runtime context.
- `decide`: explicitly confirm one eligible routine, read-only process action.
- `status`: show a persisted mission state.

Internally, Creator owns discovery and canonical cache maintenance. Runtime owns mission state, approvals, execution, recovery, and evidence. Do not use this entrypoint to auto-execute device-facing or significant actions, fill missing evidence, or override Runtime policy.

See `README.md` for the FDU Quick Start. For advanced maintenance, recovery, or Agent-directed decisions outside this entrypoint's routine read-only boundary, use the bundled `scripts/runtime.py` command; do not depend on external historical Skills.
