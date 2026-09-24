"""Restricted, validated patches for the active compact ontology graph."""
from __future__ import annotations

import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schema import load_schema
from .backup import _validate_graph_root, backup_active_graph


_DANGEROUS_FIELDS = {
    "optional_command", "optional_entrypoints", "command", "commands", "device_parameter", "device_parameters", "entrypoints",
    "execution_policy", "mission", "mission_id", "parameters", "policies", "policy",
    "runtime", "side_effect", "side_effect_level", "state", "tool_command",
}
_MISSION_TYPES = {"Mission", "SkillExecution"}
_ALLOWED_OPERATIONS = {"update_metadata", "update_entity", "add_entity", "remove_entity",
                       "add_relation", "remove_relation"}
_BLOCKED_RELATIONS = {"appliesTo", "belongsToMission", "executesSkill", "executesNode"}


def _operations(patch: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(patch, dict):
        raise ValueError("Patch must be a JSON object")
    operations = patch.get("operations")
    if operations is None and patch.get("op"):
        operations = [patch]
    if not isinstance(operations, list) or not operations:
        raise ValueError("Patch requires a non-empty operations list")
    if not all(isinstance(operation, dict) for operation in operations):
        raise ValueError("Patch operations must be objects")
    return operations


def _entity_maps(graph: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    entities: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    for record in graph:
        if "entity" in record:
            entity = record["entity"]
            if entity.get("id") in entities:
                raise ValueError(f"duplicate entity id: {entity.get('id')}")
            entities[entity["id"]] = entity
        elif "relation" in record:
            relation = record["relation"]
            if relation.get("id") in relations:
                raise ValueError(f"duplicate relation id: {relation.get('id')}")
            relations[relation["id"]] = relation
        else:
            raise ValueError("Graph records must contain entity or relation")
    return entities, relations


def _check_metadata(entity: dict[str, Any], updates: dict[str, Any]) -> None:
    if entity.get("type") in _MISSION_TYPES:
        raise ValueError("mission-state modifications are not allowed")
    if not isinstance(updates, dict) or not updates:
        raise ValueError("Metadata update requires a non-empty set")
    blocked = sorted(str(key) for key in updates if str(key).casefold() in _DANGEROUS_FIELDS)
    if blocked:
        raise ValueError(f"Fields not allowed in maintenance patches: {blocked}")
    if any(str(key) in {"id", "type"} for key in updates):
        raise ValueError("Fields not allowed in maintenance patches: ['id', 'type']")


def _check_operation_permissions(operations: list[dict[str, Any]], graph: list[dict[str, Any]]) -> None:
    entities, relations = _entity_maps(graph)
    for operation in operations:
        op = operation.get("op")
        if op not in _ALLOWED_OPERATIONS:
            raise ValueError(f"Unsupported maintenance operation: {op}")
        if op in {"update_metadata", "update_entity"}:
            entity_id = operation.get("entity_id") or operation.get("id")
            entity = entities.get(entity_id)
            if entity is None:
                raise ValueError(f"Unknown entity: {entity_id}")
            updates = operation.get("set", operation.get("properties"))
            _check_metadata(entity, updates)
        elif op == "add_entity":
            entity = operation.get("entity")
            if not isinstance(entity, dict) or not entity.get("id") or not entity.get("type"):
                raise ValueError("add_entity requires an entity with id and type")
            if entity["id"] in entities:
                raise ValueError(f"Entity already exists: {entity['id']}")
            if entity.get("type") in _MISSION_TYPES:
                raise ValueError("mission-state modifications are not allowed")
            _check_metadata(entity, entity.get("properties", {"name": entity["id"]}))
            entities[entity["id"]] = entity
        elif op == "remove_entity":
            entity_id = operation.get("entity_id") or operation.get("id")
            entity = entities.get(entity_id)
            if entity is None:
                raise ValueError(f"Unknown entity: {entity_id}")
            if entity.get("type") == "Skill":
                raise ValueError("Skill deletion is not allowed")
            if entity.get("type") in _MISSION_TYPES:
                raise ValueError("mission-state modifications are not allowed")
            entities.pop(entity_id)
        elif op == "add_relation":
            relation = operation.get("relation")
            if not isinstance(relation, dict) or not relation.get("id"):
                raise ValueError("add_relation requires a relation with id")
            if relation["id"] in relations:
                raise ValueError(f"Relation already exists: {relation['id']}")
            if relation.get("relation") in _BLOCKED_RELATIONS:
                raise ValueError("mission or policy relations are not allowed")
            relations[relation["id"]] = relation
        elif op == "remove_relation":
            relation_id = operation.get("relation_id") or operation.get("id")
            if relation_id not in relations:
                raise ValueError(f"Unknown relation: {relation_id}")
            if relations[relation_id].get("relation") in _BLOCKED_RELATIONS:
                raise ValueError("mission or policy relations are not allowed")
            relations.pop(relation_id)


def _apply_operations(graph: list[dict[str, Any]], operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = copy.deepcopy(graph)
    for operation in operations:
        op = operation["op"]
        if op in {"update_metadata", "update_entity"}:
            entity_id = operation.get("entity_id") or operation.get("id")
            updates = operation.get("set", operation.get("properties"))
            for record in result:
                if record.get("entity", {}).get("id") == entity_id:
                    record["entity"].setdefault("properties", {}).update(copy.deepcopy(updates))
                    break
        elif op == "add_entity":
            result.append({"entity": copy.deepcopy(operation["entity"])})
        elif op == "remove_entity":
            entity_id = operation.get("entity_id") or operation.get("id")
            result = [record for record in result if record.get("entity", {}).get("id") != entity_id]
        elif op == "add_relation":
            result.append({"relation": copy.deepcopy(operation["relation"])})
        elif op == "remove_relation":
            relation_id = operation.get("relation_id") or operation.get("id")
            result = [record for record in result if record.get("relation", {}).get("id") != relation_id]
    return result


def _validate_graph(graph: list[dict[str, Any]]) -> None:
    classes, relation_specs = load_schema()
    entities, relations = _entity_maps(graph)
    for entity_id, entity in entities.items():
        if entity.get("type") not in classes:
            raise ValueError(f"graph validation failed: unknown entity class {entity_id}")
    for relation in relations.values():
        relation_name = relation.get("relation")
        if relation_name not in relation_specs:
            raise ValueError(f"graph validation failed: unknown relation {relation_name}")
        source = entities.get(relation.get("source"))
        target = entities.get(relation.get("target"))
        if source is None or target is None:
            raise ValueError(f"graph validation failed: missing relation endpoint {relation.get('id')}")
        spec = relation_specs[relation_name]
        if source.get("type") not in spec.get("domain", []) or target.get("type") not in spec.get("range", []):
            raise ValueError(f"graph validation failed: invalid relation endpoint {relation.get('id')}")


def validate_patch(patch: dict[str, Any], graph: list[dict[str, Any]]) -> None:
    operations = _operations(patch)
    _check_operation_permissions(operations, graph)
    candidate = _apply_operations(graph, operations)
    _validate_graph(candidate)


def apply_patch(graph: list[dict[str, Any]], patch: dict[str, Any]) -> list[dict[str, Any]]:
    validate_patch(patch, graph)
    return _apply_operations(graph, _operations(patch))


def maintain_graph(cache_dir: Path, patch: dict[str, Any], reason: str) -> dict[str, Any]:
    cache = Path(cache_dir).resolve()
    graph_path = cache / "ontology.jsonl"
    if not graph_path.is_file():
        raise FileNotFoundError(f"active graph is unavailable: {graph_path}")
    graph = [json.loads(line) for line in graph_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    patched = apply_patch(graph, patch)
    staging = cache.parent / f".{cache.name}-maintenance-build"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(cache, staging, ignore=shutil.ignore_patterns(".backup"))
    (staging / "ontology.jsonl").write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in patched) + "\n", encoding="utf-8"
    )
    manifest_path = staging / "cache-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _validate_graph_root(staging)
    backup = backup_active_graph(cache, reason)
    shutil.copytree(cache / ".backup", staging / ".backup")
    shutil.rmtree(cache)
    staging.replace(cache)
    return {"cache_dir": str(cache), "backup": backup,
            "changed_records": len(patched) - len(graph)}
