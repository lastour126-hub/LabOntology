import json
from pathlib import Path

import pytest

from core.creator.backup import backup_active_graph
from core.creator.intake import receive_bundle
from core.creator.maintenance import apply_patch, maintain_graph, validate_patch


def _bundle(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "skills.json").write_text(json.dumps({
        "schema": "labontology.skill-bundle.v1",
        "suite_id": "suite:test",
        "skills": [{"id": "reader", "source_dir": str(tmp_path),
                     "entrypoints": [], "outputs": []}],
        "device_knowledge": [], "workflows": [],
    }), encoding="utf-8")
    (bundle / "DeviceKnowledge").mkdir()
    (bundle / "Workflow").mkdir()
    return bundle


def _graph(cache):
    return [json.loads(line) for line in (cache / "ontology.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def test_maintenance_updates_low_risk_metadata_and_keeps_backup(tmp_path):
    cache = Path(receive_bundle(_bundle(tmp_path), tmp_path)["output_dir"])

    result = maintain_graph(cache, {"operations": [{
        "op": "update_metadata", "entity_id": "skill:reader",
        "set": {"description": "Use verified local records", "preconditions": ["record exists"]},
    }]}, "learned from repeated missing input")

    skill = next(item["entity"] for item in _graph(cache)
                 if item.get("entity", {}).get("id") == "skill:reader")
    assert skill["properties"]["description"] == "Use verified local records"
    assert skill["properties"]["preconditions"] == ["record exists"]
    assert result["backup"]["reason"] == "learned from repeated missing input"
    assert (cache / ".backup" / "ontology.jsonl").is_file()


def test_maintenance_rejects_execution_and_mission_mutations(tmp_path):
    cache = Path(receive_bundle(_bundle(tmp_path), tmp_path)["output_dir"])
    graph = _graph(cache)

    for updates in (
        {"command": ["dangerous"]},
        {"side_effect_level": "device_control"},
        {"policy": {"blocked": False}},
        {"mission_id": "mission:other"},
    ):
        with pytest.raises(ValueError, match="not allowed"):
            validate_patch({"operations": [{"op": "update_metadata", "entity_id": "skill:reader", "set": updates}]}, graph)

    with pytest.raises(ValueError, match="Skill deletion"):
        validate_patch({"operations": [{"op": "remove_entity", "entity_id": "skill:reader"}]}, graph)


def test_invalid_relation_patch_does_not_change_active_graph_or_backup(tmp_path):
    cache = Path(receive_bundle(_bundle(tmp_path), tmp_path)["output_dir"])
    backup_active_graph(cache, "before invalid patch")
    before = (cache / "ontology.jsonl").read_bytes()
    backup_before = (cache / ".backup" / "ontology.jsonl").read_bytes()

    with pytest.raises(ValueError, match="validation|endpoint"):
        maintain_graph(cache, {"operations": [{
            "op": "add_relation",
            "relation": {"id": "relation:bad", "relation": "containsSkill",
                         "source": "suite:missing", "target": "skill:reader"},
        }]}, "bad patch")

    assert (cache / "ontology.jsonl").read_bytes() == before
    assert (cache / ".backup" / "ontology.jsonl").read_bytes() == backup_before
