# LabOntology Creator examples

These examples describe bundle inputs and external knowledge sources. They are not execution authorization.

- `standard-bundle/` shows the portable input bundle format. Its device and workflow files are evidence inputs only.
- `standard-user-knowledge/` shows external knowledge records that Creator can attach to a compact graph through `source-index.json`.

Creator writes the maintained result directly as `cache-manifest.json`, `ontology.jsonl`, and `source-index.json`. It does not produce a `standard-cache/` directory layout.
