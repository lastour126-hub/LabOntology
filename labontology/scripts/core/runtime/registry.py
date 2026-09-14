from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import ExecutionPolicySpec, SkillFlow, SkillSpec


def _skill_from_data(data: dict[str, Any], base_dir: Path) -> SkillSpec:
    command = data.get("command", [])
    if isinstance(command, str):
        command = command.split()
    working_dir = data.get("working_dir")
    if working_dir:
        working_dir = str((base_dir / working_dir).resolve())
    knowledge_dir = data.get("knowledge_dir")
    if knowledge_dir:
        knowledge_dir = str((base_dir / knowledge_dir).resolve())
    return SkillSpec(
        id=data["id"],
        command=list(command),
        outputs=dict(data.get("outputs", {})),
        input_artifacts=list(data.get("inputs", [])),
        required_capabilities=list(data.get("required_capabilities", [])),
        working_dir=working_dir,
        timeout_seconds=int(data.get("timeout_seconds", 300)),
        side_effect_level=data.get("side_effect_level", "read_only"),
        execution_mode=data.get("execution_mode", "process"),
        runnable=bool(data.get("runnable", bool(command))),
        argument_bindings=dict(data.get("argument_bindings", {})),
        fixed_arguments=list(data.get("fixed_arguments", [])),
        knowledge_dir=knowledge_dir,
        decision_policy=dict(data.get("decision_policy", {})),
        goal_types=list(data.get("goal_types", [])),
        triggers=list(data.get("triggers", [])),
        preconditions=list(data.get("preconditions", [])),
        failure_modes=list(data.get("failure_modes", [])),
        recommended_next_skills=list(data.get("recommended_next_skills", [])),
        retry_limit=max(0, int(data.get("retry_limit", 1))),
    )


@dataclass
class SkillSuite:
    id: str
    name: str
    root: Path
    skills: dict[str, SkillSpec]
    flow_entries: dict[str, Path | SkillFlow]
    policies: list[ExecutionPolicySpec]
    available_capabilities: set[str] = field(default_factory=set)
    skill_knowledge: dict[str, dict[str, Any]] = field(default_factory=dict)

    def skill_flow(self, flow_id: str) -> SkillFlow:
        path = self.flow_entries[flow_id]
        if isinstance(path, SkillFlow):
            return path
        return SkillFlow.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


class Registry:
    def __init__(self, suites: dict[str, SkillSuite]):
        self.suites = suites

    @classmethod
    def load(cls, path: Path) -> "Registry":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        suites: dict[str, SkillSuite] = {}
        for suite_data in data.get("suites", []):
            suite_dir = (path.parent / suite_data.get("root", ".")).resolve()
            skills_path = (path.parent / suite_data["skills_file"]).resolve()
            skills_doc = yaml.safe_load(skills_path.read_text(encoding="utf-8")) or {}
            skills = {item["id"]: _skill_from_data(item, suite_dir) for item in skills_doc.get("skills", [])}
            flow_entries = {}
            if suite_data.get("flows_file"):
                flows_path = (path.parent / suite_data["flows_file"]).resolve()
                flows_doc = yaml.safe_load(flows_path.read_text(encoding="utf-8")) or {}
                flow_entries = {
                    item["id"]: (flows_path.parent / item["file"]).resolve()
                    for item in flows_doc.get("flows", [])
                }
            knowledge = {item["id"]: {**item, "registry_file": str(path.resolve())}
                         for item in skills_doc.get("skills", [])}
            source_path = skills_path.parent / "source" / "skills.json"
            if source_path.exists():
                source = json.loads(source_path.read_text(encoding="utf-8"))
                for item in source.get("skills", []):
                    if item["id"] in skills:
                        knowledge[item["id"]] = {**knowledge.get(item["id"], {}), **item,
                                                 "source_record_file": str(source_path.resolve())}
            policies: list[ExecutionPolicySpec] = []
            if suite_data.get("policies_file"):
                policies_path = (path.parent / suite_data["policies_file"]).resolve()
                policies_doc = yaml.safe_load(policies_path.read_text(encoding="utf-8")) or {}
                policies = [
                    ExecutionPolicySpec(
                        id=item["id"],
                        applies_to=list(item.get("applies_to", [])),
                        blocked=bool(item.get("blocked", False)),
                        requires_confirmation=bool(item.get("requires_confirmation", False)),
                    )
                    for item in policies_doc.get("policies", [])
                ]
            suites[suite_data["id"]] = SkillSuite(
                id=suite_data["id"],
                name=suite_data.get("name", suite_data["id"]),
                root=suite_dir,
                skills=skills,
                flow_entries=flow_entries,
                policies=policies,
                available_capabilities=set(),
                skill_knowledge=knowledge,
            )
        return cls(suites)

    @classmethod
    def load_cache(cls, system_dir: Path) -> "Registry":
        """Load the Runtime bridge generated inside a maintained cache."""
        system_dir = system_dir.resolve()
        manifest_path = system_dir / "cache-manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Maintained cache is missing cache manifest: {manifest_path}"
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid cache manifest: {manifest_path}") from exc
        if not isinstance(manifest, dict) or not manifest.get("updated_at"):
            raise ValueError(f"Cache manifest must contain updated_at: {manifest_path}")
        compact_graph = system_dir / "ontology.jsonl"
        if compact_graph.exists():
            return cls._load_compact_cache(system_dir, compact_graph)
        raise FileNotFoundError(
            f"Maintained cache is missing canonical graph: {compact_graph}"
        )

    @classmethod
    def _load_compact_cache(cls, system_dir: Path, graph_path: Path) -> "Registry":
        entities: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []
        for line in graph_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if "entity" in record:
                entity = record["entity"]
                entities[entity["id"]] = entity
            elif "relation" in record:
                relations.append(record["relation"])
        suites: dict[str, SkillSuite] = {}
        suite_entities = [item for item in entities.values() if item.get("type") == "SkillSuite"]
        for suite_entity in suite_entities:
            suite_id = suite_entity["id"]
            skill_ids = [relation["target"] for relation in relations
                         if relation.get("relation") == "containsSkill" and relation.get("source") == suite_id]
            skills: dict[str, SkillSpec] = {}
            knowledge: dict[str, dict[str, Any]] = {}
            for skill_id in skill_ids:
                entity = entities.get(skill_id)
                if not entity:
                    continue
                props = entity.get("properties", {})
                runtime = props.get("runtime", {})
                skill_key = skill_id.split(":", 1)[-1]
                skills[skill_key] = _skill_from_data({"id": skill_key, **runtime,
                    "decision_policy": props.get("decision_policy", {}),
                    "goal_types": props.get("goal_types", []),
                    "triggers": props.get("triggers", []),
                    "preconditions": props.get("preconditions", []),
                    "failure_modes": props.get("failure_modes", []),
                    "recommended_next_skills": props.get("recommended_next_skills", []),
                }, system_dir)
                knowledge[skill_key] = {
                    "description": props.get("description"),
                    "unresolved": props.get("unresolved", []),
                    "evidence": props.get("evidence", []),
                    "confidence": props.get("confidence"),
                    "documentation": props.get("documentation", {}),
                    "instruction_source": props.get("instruction_source"),
                    "instruction_digest": props.get("instruction_digest", []),
                    "knowledge_files": props.get("knowledge_files", []),
                    "suite_id": suite_id,
                    "graph_file": str(graph_path.resolve()),
                    "registry_file": str(graph_path.resolve()),
                }
            flow_entries: dict[str, SkillFlow] = {}
            for flow_entity in entities.values():
                if flow_entity.get("type") != "SkillFlow":
                    continue
                flow_id = flow_entity["id"]
                if not any(r.get("relation") == "providesSkillFlow" and r.get("source") == suite_id and r.get("target") == flow_id for r in relations):
                    continue
                node_ids = [r["target"] for r in relations if r.get("relation") == "hasNode" and r.get("source") == flow_id]
                nodes = []
                for node_id in node_ids:
                    node_entity = entities.get(node_id)
                    if not node_entity:
                        continue
                    props = node_entity.get("properties", {})
                    nodes.append({"id": node_id, "type": props.get("node_type", "skill_call"),
                                  "skill": props.get("skill_id"), "order": props.get("order", 0),
                                  "inputs": props.get("inputs", []), "outputs": props.get("outputs", [])})
                flow_entries[flow_id] = SkillFlow.from_dict({"id": flow_id, "nodes": nodes})
            suites[suite_id] = SkillSuite(suite_id, suite_entity.get("properties", {}).get("name", suite_id),
                                          system_dir, skills, flow_entries, [],
                                          set(suite_entity.get("properties", {}).get("available_capabilities", [])), knowledge)
        if not suites:
            raise ValueError(f"Canonical graph contains no SkillSuite: {graph_path}")
        return cls(suites)

    def suite(self, suite_id: str) -> SkillSuite:
        return self.suites[suite_id]
