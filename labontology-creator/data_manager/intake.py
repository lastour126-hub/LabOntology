"""Create and maintain the compact LabOntology graph cache.

The cache is an evidence index for an agent. Workflow records are descriptive
references only; this module never turns them into a runtime schedule.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

BUNDLE_SCHEMA = "labontology.skill-bundle.v1"
CACHE_SCHEMA = "labontology.graph-cache.v1"
MAINTAINABLE_KINDS = frozenset({"knowledge", "device", "workflow"})

def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower() or "imported"

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _as_list(value: Any) -> list[Any]:
    return [] if value is None else value if isinstance(value, list) else [value]

def _skill_id(skill: dict[str, Any]) -> str:
    return str(skill.get("id") or skill.get("name") or "unknown")

def _artifact_id(value: Any) -> str:
    text = str(value.get("id") if isinstance(value, dict) else value)
    return text if text.startswith("artifact:") else f"artifact:{_safe_name(text)}"

def _normalise_outputs(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {_artifact_id(key): item for key, item in value.items()}
    result: dict[str, Any] = {}
    for item in _as_list(value):
        if isinstance(item, dict):
            name = item.get("id") or item.get("name")
            if name:
                result[_artifact_id(name)] = item.get("path") or item.get("value")
        elif item:
            result[_artifact_id(item)] = None
    return result

def _skill_outputs(skill: dict[str, Any]) -> dict[str, Any]:
    """Keep named outputs; discard a generic fallback when a concrete output exists."""
    outputs = _normalise_outputs(skill.get("outputs"))
    if len(outputs) > 1:
        outputs.pop("artifact:result", None)
    return outputs

def _explicit_output_bindings(value: Any) -> dict[str, dict[str, Any]]:
    """Read per-output invocation bindings without guessing parameter names."""
    items = value.items() if isinstance(value, dict) else enumerate(_as_list(value))
    bindings: dict[str, dict[str, Any]] = {}
    for key, item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id") or key
        binding = item.get("binding")
        if not name or not isinstance(binding, dict) or not binding.get("parameter"):
            continue
        normalized = {field: binding[field] for field in ("parameter", "flag", "positional", "additional_flags", "value") if field in binding}
        bindings[_artifact_id(name)] = normalized
    return bindings

def _declared_capabilities(root: Path) -> list[str]:
    values: set[str] = set()
    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str) and value.startswith("capability:"):
            values.add(value)
    for path in root.rglob("*") if root.exists() else []:
        if not path.is_file() or path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError):
            continue
        collect(data)
    return sorted(values)

def _source_record(path: Path, roles: list[str], skill_id: str | None = None, note: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path.resolve()), "roles": sorted(set(roles)), "sha256": _sha256(path)}
    if skill_id:
        result["skill_id"] = skill_id
    if note:
        result["note"] = note
    return result

def _runtime(skill: dict[str, Any], inferred_inputs: list[str] | None = None) -> dict[str, Any]:
    skill_id = _skill_id(skill)
    entrypoints = [Path(str(item)) for item in _as_list(skill.get("entrypoints"))]
    entrypoint = next((item for item in entrypoints if item.exists()), entrypoints[0] if entrypoints else None)
    source_dir = Path(str(skill.get("source_dir") or (entrypoint.parent if entrypoint else "."))).resolve()
    if entrypoint and entrypoint.is_relative_to(source_dir):
        command = ["python", entrypoint.relative_to(source_dir).as_posix()]
    else:
        command = ["python", str(entrypoint)] if entrypoint else []
    inputs = list(dict.fromkeys([_artifact_id(item) for item in _as_list(skill.get("inputs"))] + list(inferred_inputs or [])))
    outputs = _skill_outputs(skill)
    bindings: dict[str, dict[str, Any]] = {"inputs": {}, "outputs": {
        artifact: binding for artifact, binding in _explicit_output_bindings(skill.get("outputs")).items()
        if artifact in outputs
    }}
    for parameter in _as_list(skill.get("parameters")):
        if not isinstance(parameter, dict) or not parameter.get("name"):
            continue
        name = str(parameter["name"])
        binding = {"parameter": name, "positional": True} if parameter.get("positional") else {"parameter": name, "flag": "--" + name.replace("_", "-")}
        normalized = _safe_name(name)
        for artifact in inputs:
            if artifact not in bindings["outputs"] and _safe_name(artifact.removeprefix("artifact:")) == normalized:
                bindings["inputs"][artifact] = binding
        for artifact in outputs:
            if _safe_name(artifact.removeprefix("artifact:")) == normalized:
                bindings["outputs"][artifact] = binding
    output_parameters = [item for item in _as_list(skill.get("parameters"))
                         if isinstance(item, dict) and item.get("name")
                         and re.search(r"(?:^|_)(?:output|result)(?:_|$)", str(item["name"]), re.I)]
    for parameter in output_parameters:
        name = str(parameter["name"])
        formats = [value for value in ("csv", "json", "yaml", "yml", "md", "txt") if value in name.lower()]
        if not formats:
            continue
        for artifact, location in outputs.items():
            if artifact in bindings["outputs"] or not any(value in str(location).lower() for value in formats):
                continue
            bindings["outputs"][artifact] = (
                {"parameter": name, "positional": True} if parameter.get("positional")
                else {"parameter": name, "flag": "--" + name.replace("_", "-")}
            )
            break
    unbound_outputs = [artifact for artifact in outputs if artifact not in bindings["outputs"]]
    if len(unbound_outputs) == 1 and len(output_parameters) == 1:
        parameter = output_parameters[0]
        name = str(parameter["name"])
        bindings["outputs"][unbound_outputs[0]] = (
            {"parameter": name, "positional": True} if parameter.get("positional")
            else {"parameter": name, "flag": "--" + name.replace("_", "-")}
        )
    runtime_outputs = outputs if not output_parameters else {artifact: outputs[artifact] for artifact in bindings["outputs"]}
    return {"id": skill_id, "name": str(skill.get("name") or skill_id), "command": command,
            "fixed_arguments": _as_list(skill.get("fixed_arguments")), "inputs": inputs, "outputs": runtime_outputs,
            "parameters": [item for item in _as_list(skill.get("parameters")) if isinstance(item, dict)],
            "argument_bindings": {key: value for key, value in bindings.items() if value},
            "required_capabilities": [str(item) for item in _as_list(skill.get("required_capabilities"))],
            "side_effect_level": str(skill.get("side_effect_level") or "read_only"),
            "execution_mode": str(skill.get("execution_mode") or "process"), "runnable": bool(command),
            "working_dir": str(source_dir), "timeout_seconds": int(skill.get("timeout_seconds") or 300)}

def _entity(identifier: str, entity_type: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {"entity": {"id": identifier, "type": entity_type, "properties": properties}}

def _relation(relation_type: str, source: str, target: str) -> dict[str, Any]:
    key = hashlib.sha256(f"{relation_type}|{source}|{target}".encode()).hexdigest()[:12]
    return {"relation": {"id": f"rel:{relation_type}:{key}", "relation": relation_type, "source": source, "target": target}}

def _workflow_records(skills: list[dict[str, Any]], workflows: list[dict[str, Any]], suite_id: str,
                      dependencies: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Store workflow knowledge as a reference, never as a scheduler instruction."""
    known = {_skill_id(skill) for skill in skills}
    if not workflows:
        workflows = [{"id": f"flow:{_safe_name(suite_id)}", "nodes": [
            {"id": _skill_id(skill), "skill": _skill_id(skill), "depends_on": (dependencies or {}).get(_skill_id(skill), _as_list(skill.get("dependencies")))}
            for skill in sorted(skills, key=_skill_id)
        ], "inferred": True}]
    records: list[dict[str, Any]] = []
    for workflow in workflows:
        flow_id = str(workflow.get("id") or f"flow:{_safe_name(suite_id)}")
        if not flow_id.startswith("flow:"):
            flow_id = f"flow:{_safe_name(flow_id)}"
        inferred = bool(workflow.get("inferred", not workflow.get("nodes")))
        records.append(_entity(flow_id, "SkillFlow", {"name": str(workflow.get("name") or f"{suite_id} workflow reference"), "status": "reference_only", "inferred": inferred, "inference_basis": _as_list(workflow.get("inference_basis")) or ["declared workflow" if not inferred else "Skill metadata"]}))
        nodes = [node for node in _as_list(workflow.get("nodes")) if isinstance(node, dict)]
        for node in nodes:
            skill_id = str(node.get("skill") or node.get("skill_id") or "")
            if skill_id not in known:
                continue
            node_id = f"flow-node:{_safe_name(flow_id.removeprefix('flow:'))}:{_safe_name(str(node.get('id') or skill_id))}"
            records.extend([_entity(node_id, "FlowNode", {"skill_id": skill_id}), _relation("hasNode", flow_id, node_id), _relation("calls", node_id, f"skill:{skill_id}")])
            for dependency in _as_list(node.get("depends_on")):
                predecessor = f"flow-node:{_safe_name(flow_id.removeprefix('flow:'))}:{_safe_name(str(dependency))}"
                records.append(_relation("precedes", predecessor, node_id))
    return records

def _graph_records(bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    skills = [item for item in _as_list(bundle.get("skills")) if isinstance(item, dict)]
    suite_id = str(bundle["suite_id"])
    device_root = Path(str(bundle["_bundle_dir"])) / "DeviceKnowledge"
    available_capabilities = set(_declared_capabilities(device_root))
    available_capabilities.update(
        str(capability) for skill in skills for capability in _as_list(skill.get("required_capabilities"))
        if str(capability).startswith("capability:")
    )
    records: list[dict[str, Any]] = [_entity(suite_id, "SkillSuite", {"name": suite_id, "skill_count": len(skills), "status": "maintained", "available_capabilities": sorted(available_capabilities)})]
    sources: list[dict[str, Any]] = []
    outputs_by_skill = {_skill_id(skill): _skill_outputs(skill) for skill in skills}
    known_skill_ids = set(outputs_by_skill)
    dependency_map: dict[str, list[str]] = {}
    for skill in skills:
        documentation = skill.get("documentation") if isinstance(skill.get("documentation"), dict) else {}
        references = [str(item) for item in _as_list(skill.get("dependencies"))]
        references.extend(str(item) for item in _as_list(documentation.get("related_skill_refs")))
        input_text = "\n".join(str(item).lower() for item in _as_list(documentation.get("input_hints")))
        for candidate in known_skill_ids:
            forms = {candidate.lower(), candidate.lower().replace("-", " "), candidate.lower().replace("-", "_")}
            if any(form in input_text for form in forms):
                references.append(candidate)
        dependency_map[_skill_id(skill)] = list(dict.fromkeys(item for item in references if item in known_skill_ids and item != _skill_id(skill)))
    for skill in skills:
        skill_id = _skill_id(skill)
        dependency_inputs = [artifact for dependency in dependency_map[skill_id]
                             for artifact in outputs_by_skill.get(str(dependency), {})]
        runtime = _runtime(skill, dependency_inputs)
        unbound_outputs = sorted(set(_skill_outputs(skill)) - set(runtime["outputs"]))
        unresolved = list(_as_list(skill.get("unresolved"))) + [
            f"runtime output binding missing: {artifact}" for artifact in unbound_outputs
        ]
        properties = {"name": str(skill.get("name") or skill_id), "description": skill.get("description"), "status": str(skill.get("status") or "draft"), "validated": bool(skill.get("validated", False)), "enabled": bool(skill.get("enabled", False)), "execution_mode": runtime["execution_mode"], "runnable": runtime["runnable"], "side_effect_level": runtime["side_effect_level"], "required_capabilities": runtime["required_capabilities"], "entrypoints": [str(item) for item in _as_list(skill.get("entrypoints"))], "unresolved": list(dict.fromkeys(unresolved)), "runtime": runtime}
        for key in ("documentation", "knowledge_files", "capability_evidence", "recommended_next_skills", "output_mode", "decision_policy"):
            if skill.get(key) not in ({}, [], None):
                properties[key] = skill[key]
        records.extend([_entity(f"skill:{skill_id}", "Skill", properties), _relation("containsSkill", suite_id, f"skill:{skill_id}"), _entity(f"contract:compact-{_safe_name(skill_id)}", "SkillContract", {"skill_id": skill_id, "parameters": runtime["parameters"], "input_artifacts": runtime["inputs"], "outputs": runtime["outputs"]}), _relation("hasContract", f"skill:{skill_id}", f"contract:compact-{_safe_name(skill_id)}")])
        for artifact in runtime["inputs"]:
            artifact_type = f"artifact-type:{_safe_name(artifact.removeprefix('artifact:'))}"
            records.extend([_entity(artifact_type, "ArtifactType", {"name": artifact}), _relation("contractRequires", f"contract:compact-{_safe_name(skill_id)}", artifact_type)])
        for artifact, location in runtime["outputs"].items():
            artifact_type = f"artifact-type:{_safe_name(artifact.removeprefix('artifact:'))}"
            properties = {"name": artifact}
            if location is not None:
                properties["path"] = location
            records.extend([_entity(artifact_type, "ArtifactType", properties), _relation("contractProduces", f"contract:compact-{_safe_name(skill_id)}", artifact_type)])
        source_dir = Path(str(skill.get("source_dir") or runtime["working_dir"]))
        if source_dir.exists():
            for path in sorted(source_dir.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    sources.append(_source_record(path, ["skill_source"], skill_id))
        for raw in _as_list(skill.get("entrypoints")):
            path = Path(str(raw))
            if path.exists():
                sources.append(_source_record(path, ["entrypoint"], skill_id))
        for item in _as_list(skill.get("knowledge_files")):
            if isinstance(item, dict) and item.get("path"):
                path = source_dir / str(item["path"])
                if path.exists():
                    sources.append(_source_record(path, ["knowledge"], skill_id))
    workflow_records = _workflow_records(skills, [item for item in _as_list(bundle.get("workflows")) if isinstance(item, dict)], suite_id, dependency_map)
    records.extend(workflow_records)
    for record in workflow_records:
        entity = record.get("entity", {})
        if entity.get("type") == "SkillFlow":
            records.append(_relation("providesSkillFlow", suite_id, entity["id"]))
    for folder, role in (("DeviceKnowledge", "device_knowledge"), ("Workflow", "workflow")):
        root = Path(str(bundle["_bundle_dir"])) / folder
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    sources.append(_source_record(path, [role]))
    merged: dict[str, dict[str, Any]] = {}
    for item in sources:
        existing = merged.get(item["path"])
        if existing:
            existing["roles"] = sorted(set(existing["roles"]) | set(item["roles"]))
        else:
            merged[item["path"]] = item
    entities: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    for record in records:
        if "entity" in record:
            entity = record["entity"]
            previous = entities.get(entity["id"])
            if previous is None:
                entities[entity["id"]] = entity
            else:
                previous["properties"].update({key: value for key, value in entity.get("properties", {}).items() if value not in (None, [], {})})
        else:
            relation = record["relation"]
            relations.setdefault(relation["id"], relation)
    return ([{"entity": entity} for entity in entities.values()] + [{"relation": relation} for relation in relations.values()], list(merged.values()))

def _write_compact_cache(cache: Path, bundle: dict[str, Any]) -> None:
    staging = cache.parent / f".{cache.name}-graph-build"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    records, sources = _graph_records(bundle)
    (staging / "runs").mkdir()
    (staging / "ontology.jsonl").write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
    (staging / "source-index.json").write_text(json.dumps({"schema": "labontology.source-index.v1", "sources": sources}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    timestamp = _now()
    manifest = {"schema": CACHE_SCHEMA, "suite_id": bundle["suite_id"], "created_at": timestamp, "updated_at": timestamp, "cache_format": "graph-v1", "entity_count": sum("entity" in item for item in records), "relation_count": sum("relation" in item for item in records)}
    (staging / "cache-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if cache.exists():
        shutil.rmtree(cache)
    staging.replace(cache)

def receive_bundle(bundle_dir: Path, workdir: Path | None = None) -> dict[str, Any]:
    bundle_dir = Path(bundle_dir).resolve()
    payload_path = bundle_dir / "skills.json"
    if not payload_path.is_file():
        raise FileNotFoundError(f"bundle payload is missing: {payload_path}")
    bundle = json.loads(payload_path.read_text(encoding="utf-8"))
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise ValueError(f"unsupported bundle schema: {bundle.get('schema')!r}")
    suite_id = bundle.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id:
        raise ValueError("bundle suite_id is required")
    bundle["_bundle_dir"] = str(bundle_dir)
    cache = Path(workdir or Path.cwd()).resolve() / f"labontology_{_safe_name(suite_id.removeprefix('suite:'))}_skill_cache"
    _write_compact_cache(cache, bundle)
    return {"output_dir": str(cache), "cache_format": "graph-v1", "suite_id": suite_id}

def maintain_cache(cache_dir: Path, source: Path, *, kind: str = "knowledge", skill_id: str | None = None, note: str | None = None) -> dict[str, Any]:
    if kind not in MAINTAINABLE_KINDS:
        raise ValueError(f"unsupported maintenance kind: {kind}")
    cache, source = Path(cache_dir).resolve(), Path(source).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source is not a file: {source}")
    index_path, graph_path = cache / "source-index.json", cache / "ontology.jsonl"
    if not index_path.is_file() or not graph_path.is_file():
        raise FileNotFoundError("cache must contain ontology.jsonl and source-index.json")
    role = {"knowledge": "knowledge", "device": "device_knowledge", "workflow": "workflow"}[kind]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["sources"] = [item for item in index.get("sources", []) if item.get("path") != str(source)] + [_source_record(source, [role], skill_id, note)]
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = cache / "cache-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["updated_at"] = _now()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if skill_id:
        graph = [json.loads(line) for line in graph_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for record in graph:
            entity = record.get("entity", {})
            if entity.get("id") == f"skill:{skill_id}":
                item = {"path": str(source), "kind": kind}
                if note:
                    item["note"] = note
                existing = entity.setdefault("properties", {}).setdefault("maintenance_sources", [])
                existing[:] = [entry for entry in existing if entry.get("path") != str(source)] + [item]
                break
        else:
            raise ValueError(f"unknown skill_id: {skill_id}")
        graph_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in graph) + "\n", encoding="utf-8")
    return {"cache_dir": str(cache), "source_index": "source-index.json", "path": str(source), "kind": kind}
