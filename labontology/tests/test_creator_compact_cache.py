import json
from pathlib import Path

from core.creator.intake import receive_bundle


def _write_bundle(root: Path) -> Path:
    bundle = root / "bundle"
    bundle.mkdir()
    source = root / "source-skill"
    source.mkdir()
    script = source / "run.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    knowledge = source / "guide.md"
    knowledge.write_text("evidence", encoding="utf-8")
    (bundle / "skills.json").write_text(json.dumps({
        "schema": "labontology.skill-bundle.v1",
        "suite_id": "suite:compact",
        "skills": [{
            "id": "lookup",
            "name": "lookup",
            "source_dir": str(source),
            "entrypoints": [str(script)],
            "knowledge_files": [{"path": "guide.md", "format": "markdown"}],
            "documentation": {"files": [str(knowledge)]},
            "status": "draft",
            "enabled": False,
        }],
        "device_knowledge": [],
        "workflows": [],
    }), encoding="utf-8")
    return bundle


def test_receive_bundle_creates_one_canonical_graph_and_source_index(tmp_path):
    result = receive_bundle(_write_bundle(tmp_path), tmp_path / "workdir")
    cache = Path(result["output_dir"])

    assert result["cache_format"] == "graph-v1"
    assert {item.name for item in cache.iterdir()} == {
        "cache-manifest.json", "ontology.jsonl", "source-index.json", "runs"
    }
    graph = [json.loads(line) for line in (cache / "ontology.jsonl").read_text(encoding="utf-8").splitlines()]
    skill = next(record["entity"] for record in graph if record.get("entity", {}).get("id") == "skill:lookup")
    assert skill["properties"]["runtime"]["command"][-1] == "run.py"
    assert skill["properties"]["execution_mode"] == skill["properties"]["runtime"]["execution_mode"]
    index = json.loads((cache / "source-index.json").read_text(encoding="utf-8"))
    roles = {role for record in index["sources"] for role in record["roles"]}
    assert roles >= {"skill_source", "entrypoint", "knowledge"}
    assert all(record["sha256"] for record in index["sources"])
    assert all("role" not in record and "skill_ids" not in record for record in index["sources"])
    assert all("skill_id" in record for record in index["sources"])
    assert not any(cache.rglob("guide.md"))


def test_compact_contract_keeps_only_interface_fields_and_omits_empty_decision_fields(tmp_path):
    result = receive_bundle(_write_bundle(tmp_path), tmp_path / "workdir")
    graph = [json.loads(line) for line in (Path(result["output_dir"]) / "ontology.jsonl").read_text(encoding="utf-8").splitlines()]
    contract = next(record["entity"] for record in graph if record.get("entity", {}).get("id") == "contract:compact-lookup")
    assert set(contract["properties"]) == {"skill_id", "parameters", "input_artifacts", "outputs"}
    skill = next(record["entity"] for record in graph if record.get("entity", {}).get("id") == "skill:lookup")
    assert "goal_types" not in skill["properties"]
    assert "failure_modes" not in skill["properties"]

