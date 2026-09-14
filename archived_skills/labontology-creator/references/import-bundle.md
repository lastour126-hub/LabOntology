# Importing a LabOntology bundle

`labontology.skill-bundle.v1` contains `skills.json` and may include source knowledge, device evidence, or workflow-reference files. These inputs are analyzed as evidence; they do not define a runtime execution sequence or grant permission to invoke a Skill.

Import with:

```powershell
python scripts/import_bundle.py C:\path\to\bundle --workdir C:\path\to\workspace
```

The result is one compact cache per suite:

```text
labontology_<suite>_skill_cache/
├── cache-manifest.json
├── ontology.jsonl
├── source-index.json
└── runs/
```

`ontology.jsonl` is the canonical graph. It stores Skill contracts, runtime bindings, ArtifactTypes, capabilities, evidence summaries, policies and optional workflow references. `source-index.json` points to original files and hashes them; the importer does not copy source packages, KBs, device documents, or workflow files into the cache.

Creator derives `SkillFlow` and `FlowNode` reference entities from explicit workflow evidence, Skill contracts and artifact dependencies. Each derived path records whether it was inferred and why. Runtime never executes it as a fixed order; the host Agent chooses the next Skill from the graph for each mission state.

Use `scripts/update_cache.py` to attach a user-provided external source. The update records its path, hash, role and optional `skill_id` in `source-index.json`; it does not create a derived cache directory or enable a Skill.
