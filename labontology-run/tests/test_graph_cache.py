import json
import sys
from types import SimpleNamespace

from runtime.commands import build_agent_runtime
from runtime.registry import Registry


def _write_graph_cache(root):
    cache = root / "cache"
    cache.mkdir()
    (cache / "cache-manifest.json").write_text(json.dumps({
        "schema": "labontology.skill-cache.graph.v1", "suite_id": "suite:graph", "updated_at": "2026-09-07"
    }), encoding="utf-8")
    entries = [
        {"entity": {"id": "suite:graph", "type": "SkillSuite", "properties": {
            "name": "Graph suite", "available_capabilities": ["capability:measure"]}}},
        {"entity": {"id": "skill:lookup", "type": "Skill", "properties": {
            "name": "Lookup", "description": "Find evidence", "runtime": {
                "command": [sys.executable, "-c", "print('evidence')"], "inputs": [], "outputs": {},
                "working_dir": str(root), "execution_mode": "process", "runnable": True,
                "side_effect_level": "read_only", "timeout_seconds": 30
            }, "unresolved": ["source date"], "evidence": [{"file": "source.md"}]
        }}},
        {"relation": {"id": "rel:1", "relation": "containsSkill", "source": "suite:graph", "target": "skill:lookup"}},
    ]
    (cache / "ontology.jsonl").write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
    (cache / "source-index.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    return cache


def test_registry_loads_runtime_contract_and_evidence_from_one_graph(tmp_path):
    registry = Registry.load_cache(_write_graph_cache(tmp_path))
    suite = registry.suite("suite:graph")

    assert suite.skills["lookup"].command[-1] == "print('evidence')"
    assert suite.skill_knowledge["lookup"]["description"] == "Find evidence"
    assert suite.skill_knowledge["lookup"]["unresolved"] == ["source date"]
    assert suite.flow_entries == {}
    assert suite.available_capabilities == {"capability:measure"}


def test_compact_cache_capabilities_are_available_to_agent_runtime(tmp_path):
    cache = _write_graph_cache(tmp_path)
    runtime = build_agent_runtime(SimpleNamespace(
        system_dir=str(cache), registry=None, suite=None, capability=[],
        runs_dir=str(tmp_path / "runs"), mission_id="capability-test",
    ))
    assert runtime.capabilities == {"capability:measure"}
