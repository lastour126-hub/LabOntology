import json
from pathlib import Path

import yaml

from data_manager.intake import maintain_cache, receive_bundle


def bundle(tmp_path, *, suite="suite:test", skills=None, knowledge=None):
    root = tmp_path / "bundle"
    root.mkdir(parents=True)
    skills = skills or [{"id": "reader", "name": "Reader", "source_dir": str(tmp_path),
                         "entrypoints": [], "knowledge_files": [], "status": "draft", "enabled": False}]
    (root / "skills.json").write_text(json.dumps({"schema": "labontology.skill-bundle.v1", "suite_id": suite,
        "skills": skills, "device_knowledge": [], "workflows": knowledge or []}), encoding="utf-8")
    (root / "DeviceKnowledge").mkdir()
    (root / "Workflow").mkdir()
    return root


def read_graph(cache):
    return [json.loads(line) for line in (cache / "ontology.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def test_receive_bundle_writes_compact_cache_and_runtime_contract(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    script = source / "run.py"
    script.write_text("print('ok')", encoding="utf-8")
    result = receive_bundle(bundle(tmp_path, skills=[{"id": "reader", "source_dir": str(source),
        "entrypoints": [str(script)], "parameters": [], "outputs": [], "status": "draft", "enabled": False}]), tmp_path)
    cache = Path(result["output_dir"])
    assert result["cache_format"] == "graph-v1"
    assert {p.name for p in cache.iterdir()} == {"cache-manifest.json", "ontology.jsonl", "source-index.json", "runs"}
    skill = next(x["entity"] for x in read_graph(cache) if x.get("entity", {}).get("id") == "skill:reader")
    assert skill["properties"]["runtime"]["working_dir"] == str(source.resolve())
    assert any("entrypoint" in x["roles"] for x in json.loads((cache / "source-index.json").read_text())["sources"])


def test_compact_maintenance_links_external_source_without_copy(tmp_path):
    cache = Path(receive_bundle(bundle(tmp_path), tmp_path)["output_dir"])
    source = tmp_path / "user.md"
    source.write_text("verified rule", encoding="utf-8")
    result = maintain_cache(cache, source, kind="knowledge", skill_id="reader", note="user evidence")
    assert result["source_index"] == "source-index.json"
    assert not (cache / "user.md").exists()
    index = json.loads((cache / "source-index.json").read_text())
    record = next(item for item in index["sources"] if item["path"] == str(source.resolve()))
    assert record["roles"] == ["knowledge"] and record["sha256"]
    graph = read_graph(cache)
    skill = next(x["entity"] for x in graph if x.get("entity", {}).get("id") == "skill:reader")
    assert skill["properties"]["maintenance_sources"][0]["path"] == str(source.resolve())


def test_compact_reimport_replaces_generated_cache(tmp_path):
    cache = Path(receive_bundle(bundle(tmp_path, suite="suite:one"), tmp_path)["output_dir"])
    stale = cache / "stale.txt"
    stale.write_text("generated", encoding="utf-8")
    second = receive_bundle(bundle(tmp_path / "second", suite="suite:one"), tmp_path)
    assert second["output_dir"] == str(cache)
    assert not stale.exists()


def test_each_suite_gets_a_separate_compact_cache(tmp_path):
    first = receive_bundle(bundle(tmp_path / "one", suite="suite:one"), tmp_path)
    second = receive_bundle(bundle(tmp_path / "two", suite="suite:two"), tmp_path)
    assert first["output_dir"] != second["output_dir"]
    assert (Path(first["output_dir"]) / "ontology.jsonl").exists()
    assert (Path(second["output_dir"]) / "ontology.jsonl").exists()


def test_graph_preserves_explicit_workflow_as_reference(tmp_path):
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "skills.json").write_text(json.dumps({"schema": "labontology.skill-bundle.v1", "suite_id": "suite:flow",
        "skills": [{"id": "a", "source_dir": str(tmp_path), "entrypoints": [], "outputs": [], "enabled": False}],
        "device_knowledge": [], "workflows": [{"id": "flow:user", "nodes": [{"id": "n", "skill": "a", "order": 1}]}]}), encoding="utf-8")
    (root / "DeviceKnowledge").mkdir()
    (root / "Workflow").mkdir()
    cache = Path(receive_bundle(root, tmp_path)["output_dir"])
    graph = read_graph(cache)
    assert any(x.get("entity", {}).get("type") == "SkillFlow" for x in graph)
