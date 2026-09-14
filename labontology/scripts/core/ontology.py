"""Small local validator and query tool for LabOntology JSONL data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ROOT / "references" / "ontology" / "classes.yaml"
RELATIONS = ROOT / "references" / "ontology" / "relations.yaml"


def load_graph(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    entities: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if "entity" in record:
            entity = record["entity"]
            entities[entity["id"]] = entity
        elif "relation" in record:
            relations.append(record["relation"])
        else:
            raise ValueError(f"Line {number}: expected entity or relation")
    return entities, relations


def load_ontology() -> tuple[dict[str, Any], dict[str, Any]]:
    classes_doc = yaml.safe_load(CLASSES.read_text(encoding="utf-8")) or {}
    relations_doc = yaml.safe_load(RELATIONS.read_text(encoding="utf-8")) or {}
    return classes_doc.get("classes", {}), relations_doc.get("relations", {})


def graph_paths(graph_name: str | None = None, system_dir: Path | None = None) -> list[Path]:
    if system_dir is None:
        return []
    compact = system_dir / "ontology.jsonl"
    if compact.exists():
        if graph_name and Path(graph_name).name not in {"ontology", "ontology.jsonl"}:
            return []
        return [compact]
    graph_dir = system_dir / "Graph"
    if graph_name:
        path = graph_dir / graph_name
        if path.suffix != ".jsonl":
            path = path.with_suffix(".jsonl")
        return [path] if path.exists() else []
    return sorted(graph_dir.glob("*.jsonl"))


def validate(graph_name: str | None = None, system_dir: Path | None = None) -> int:
    classes, relation_specs = load_ontology()
    errors: list[str] = []
    total_entities = total_relations = 0
    paths = graph_paths(graph_name, system_dir)
    for path in paths:
        entities, relations = load_graph(path)
        total_entities += len(entities)
        total_relations += len(relations)
        for entity_id, entity in entities.items():
            if entity.get("type") not in classes:
                errors.append(f"[{path.name}] Unknown entity class: {entity_id} -> {entity.get('type')}")
        for relation in relations:
            relation_name = relation.get("relation")
            if relation_name not in relation_specs:
                errors.append(f"[{path.name}] Unknown relation: {relation_name}")
                continue
            for endpoint in ("source", "target"):
                if relation.get(endpoint) not in entities:
                    errors.append(f"[{path.name}] Missing {endpoint} endpoint: {relation.get(endpoint)}")
            source = entities.get(relation.get("source"))
            target = entities.get(relation.get("target"))
            spec = relation_specs[relation_name]
            if source and source.get("type") not in spec.get("domain", []):
                errors.append(f"[{path.name}] Invalid domain for {relation_name}: {source.get('type')} -> {relation.get('source')}")
            if target and target.get("type") not in spec.get("range", []):
                errors.append(f"[{path.name}] Invalid range for {relation_name}: {relation.get('target')} -> {target.get('type')}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Valid: {len(paths)} graph(s), {total_entities} entities, {total_relations} relations")
    return 0


def query(entity_type: str | None, graph_name: str | None, system_dir: Path | None = None) -> int:
    for path in graph_paths(graph_name, system_dir):
        entities, _ = load_graph(path)
        for entity in entities.values():
            if entity_type is None or entity.get("type") == entity_type:
                print(json.dumps({"graph": path.stem, "entity": entity}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LabOntology local graph tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--graph")
    validate_parser.add_argument("--system-dir", type=Path)
    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--type")
    query_parser.add_argument("--graph")
    query_parser.add_argument("--system-dir", type=Path)
    args = parser.parse_args()
    if args.system_dir is None:
        parser.error("--system-dir is required; Runtime reads only an active Skill cache")
    return validate(args.graph, args.system_dir) if args.command == "validate" else query(args.type, args.graph, args.system_dir)


if __name__ == "__main__":
    raise SystemExit(main())
