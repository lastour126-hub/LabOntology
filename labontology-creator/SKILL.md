---
name: labontology-creator
description: Use when importing, normalizing, validating, updating, or maintaining LabOntology data from heterogeneous laboratory Skill packages and knowledge sources.
---

# LabOntology Creator

`labontology-creator` converts heterogeneous laboratory Skill packages into one compact, queryable knowledge graph for `labontology-run`. It scans and analyzes files without executing discovered scripts or contacting devices.

## Responsibilities

- Scan `SKILL.md`, README, manifests, scripts, configuration and knowledge files.
- Extract parameters, input/output contracts, capabilities, dependencies, side effects, workflow hints, evidence, confidence and unresolved fields.
- Generate a standard `labontology.skill-bundle.v1` bundle.
- Import a bundle into one maintained cache with a canonical `ontology.jsonl` and `source-index.json`.
- Preserve source paths, SHA-256 hashes, evidence locations and update metadata; do not copy large source knowledge files into the cache.
- Add user-provided knowledge as external source records and graph annotations; do not silently replace existing evidence.

## Compact cache contract

Each suite cache has only:

```text
labontology_<suite>_skill_cache/
├── cache-manifest.json
├── ontology.jsonl
├── source-index.json
└── runs/
```

`ontology.jsonl` is the canonical normalized graph. It contains `SkillSuite`, `Skill`, `SkillContract`, `ArtifactType`, `Capability`, optional `SkillFlow`/`FlowNode`, policies, evidence summaries and runtime bindings. `source-index.json` contains external source paths and hashes; source `SKILL.md`, KB files and scripts remain in their original package directories. `runs/` belongs to Runtime and is never imported knowledge.

Do not create or restore `Skills/`, `Graph/`, `Workflow/`, or `DeviceKnowledge/` directories. They were a previous derived layout and are not supported by current cache maintenance.

## Commands

```powershell
python -m data_manager.cli <skill-root> --output import-report.json
python -m data_manager.cli <skill-root> --bundle-dir <bundle-dir> --suite-id <suite-id>
python scripts/import_bundle.py <bundle-dir> --workdir <workdir>
python scripts/update_cache.py --cache-dir <cache-dir> --source <knowledge-file> --kind knowledge --skill-id <skill-id> --note "source note"
```

`--kind` is `knowledge`, `device`, or `workflow`; all three add a hashed external source record. `skill_id` links the record to a Skill for general knowledge. Device and workflow records remain graph evidence and do not become forced runtime steps.

## Boundaries and safety

Creator owns importing and canonical graph maintenance. Runtime owns mission decisions, Skill invocation and `runs/` records. Creator does not plan a mission, invoke a Skill, connect a device, or treat an entrypoint as execution authorization. Runtime does not rewrite the canonical graph during a run.

Unknown or ambiguous information goes into `unresolved` with evidence and confidence. A discovered command is not automatically enabled. Source hashes allow Runtime/Creator to identify stale evidence after a package changes. Persistent source updates remain auditable and do not fabricate missing values.

## Output

The importer returns the cache path, `cache_format: graph-v1`, graph summary, source-index path and Skill count. Validate the generated graph with `python scripts/ontology.py validate --system-dir <cache-dir>` from `labontology-run`; inspect source files by the paths listed in `source-index.json`.
