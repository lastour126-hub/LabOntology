# Standard LabOntology data bundle

LabOntology Creator emits a directory with this shape:

```text
bundle/
  skills.json
  Knowledge/<skill-id>/              # copied KB/references knowledge assets
  DeviceKnowledge/
  Workflow/
```

`skills.json` uses schema `labontology.skill-bundle.v1` and contains `suite_id`, `skills`, `device_knowledge`, and `workflows`. Each skill is a draft: `status: draft`, `validated: false`, and `enabled: false`.

Every Skill uses one common shape. Its execution boundary is described by `parameters`, `outputs`, `required_capabilities`, `dependencies`, and `side_effect_level`. These fields do not classify a Skill as software or hardware; they describe how it can be called and what it may affect. `required_capabilities` is taken first from the Skill's explicit manifest and can also be derived from strong structured action identifiers in the Skill's own knowledge files. Each derived value is recorded in `capability_evidence` with its source and confidence; Skill names alone never create a capability. `DeviceKnowledge` and `Workflow` are optional and are only attached when supported by source evidence.

LabOntology Creator preserves explicit manifest values and does not infer device relations or Skill types from names. It also indexes Markdown sections, CLI evidence, and supported JSON/YAML/CSV/Markdown files under `KB`, `references`, and related knowledge directories. Unknown or unconfirmed values are represented in `unresolved`; source files, parsed summaries, and extraction methods are recorded in `evidence`. `Knowledge/` is an optional import input: Creator records original source paths and hashes in the maintained cache instead of copying the assets into it.

The bundle is input for Creator cache maintenance. It is not an execution registry and must not be treated as permission to run a command or contact a device.
