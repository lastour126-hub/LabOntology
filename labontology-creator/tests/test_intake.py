import hashlib
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


def test_import_records_skill_document_hash_and_actionable_digest(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    document = source / "SKILL.md"
    document.write_text("# Tool\n## 前提\n- 输入已核实。\n## 约束\n- 不得猜测输出路径。\n", encoding="utf-8")
    cache = Path(receive_bundle(bundle(tmp_path, skills=[{
        "id": "reader", "source_dir": str(source), "entrypoints": [], "outputs": [], "enabled": False,
        "documentation": {"precondition_hints": ["输入已核实。"], "constraint_hints": ["不得猜测输出路径。"]},
    }]), tmp_path)["output_dir"])
    skill = next(x["entity"] for x in read_graph(cache) if x.get("entity", {}).get("id") == "skill:reader")
    assert skill["properties"]["instruction_source"] == {
        "path": str(document.resolve()),
        "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
    }
    assert skill["properties"]["instruction_digest"] == ["输入已核实。", "不得猜测输出路径。"]


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


def test_import_binds_a_single_declared_output_to_output_parameter(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    script = source / "run.py"
    script.write_text("print('ok')", encoding="utf-8")
    cache = Path(receive_bundle(bundle(tmp_path, skills=[{
        "id": "writer", "source_dir": str(source), "entrypoints": [str(script)],
        "parameters": [{"name": "output", "required": True}],
        "outputs": [{"name": "artifact:report", "path": "outputs/report.json"}],
        "status": "draft", "enabled": False,
    }]), tmp_path)["output_dir"])
    skill = next(x["entity"] for x in read_graph(cache) if x.get("entity", {}).get("id") == "skill:writer")
    assert skill["properties"]["runtime"]["argument_bindings"]["outputs"] == {
        "artifact:report": {"parameter": "output", "flag": "--output"}
    }


def test_import_binds_format_specific_output_parameter(tmp_path):
    cache = Path(receive_bundle(bundle(tmp_path, skills=[{
        "id": "writer", "source_dir": str(tmp_path), "entrypoints": [],
        "parameters": [{"name": "output"}, {"name": "csv_output"}],
        "outputs": [
            {"name": "artifact:report", "path": "outputs/report.json"},
            {"name": "artifact:table", "path": "outputs/table.csv"},
        ], "enabled": False,
    }]), tmp_path)["output_dir"])
    skill = next(x["entity"] for x in read_graph(cache) if x.get("entity", {}).get("id") == "skill:writer")
    assert skill["properties"]["runtime"]["argument_bindings"]["outputs"]["artifact:table"] == {
        "parameter": "csv_output", "flag": "--csv-output"
    }
    assert skill["properties"]["runtime"]["outputs"] == {"artifact:table": "outputs/table.csv"}
    assert "runtime output binding missing: artifact:report" in skill["properties"]["unresolved"]


def test_import_prefers_explicit_output_binding_over_name_inference(tmp_path):
    cache = Path(receive_bundle(bundle(tmp_path, skills=[{
        "id": "writer", "source_dir": str(tmp_path), "entrypoints": [],
        "parameters": [{"name": "destination"}, {"name": "output"}],
        "outputs": [{
            "name": "artifact:output", "path": "outputs/report.json",
            "binding": {"parameter": "destination", "flag": "--destination"},
        }], "enabled": False,
    }]), tmp_path)["output_dir"])
    skill = next(x["entity"] for x in read_graph(cache) if x.get("entity", {}).get("id") == "skill:writer")
    assert skill["properties"]["runtime"]["argument_bindings"]["outputs"] == {
        "artifact:output": {"parameter": "destination", "flag": "--destination"}
    }
    assert skill["properties"]["runtime"]["outputs"] == {"artifact:output": "outputs/report.json"}


def test_import_derives_dependency_artifacts_and_reference_edge(tmp_path):
    skills = [
        {"id": "producer", "source_dir": str(tmp_path), "entrypoints": [],
         "outputs": [{"name": "artifact:report", "path": "outputs/report.json"}], "enabled": False},
        {"id": "consumer", "source_dir": str(tmp_path), "entrypoints": [],
         "outputs": [], "dependencies": ["producer"], "enabled": False},
    ]
    cache = Path(receive_bundle(bundle(tmp_path, skills=skills), tmp_path)["output_dir"])
    graph = read_graph(cache)
    consumer = next(x["entity"] for x in graph if x.get("entity", {}).get("id") == "skill:consumer")
    assert consumer["properties"]["runtime"]["inputs"] == ["artifact:report"]
    assert any(x.get("relation", {}).get("relation") == "precedes" for x in graph)


def test_import_derives_input_from_an_explicit_documented_skill_reference(tmp_path):
    skills = [
        {"id": "producer", "source_dir": str(tmp_path), "entrypoints": [],
         "outputs": [{"name": "artifact:report", "path": "outputs/report.json"}], "enabled": False},
        {"id": "consumer", "source_dir": str(tmp_path), "entrypoints": [], "outputs": [], "enabled": False,
         "documentation": {"input_hints": ["producer JSON"], "related_skill_refs": []}},
    ]
    cache = Path(receive_bundle(bundle(tmp_path, skills=skills), tmp_path)["output_dir"])
    graph = read_graph(cache)
    consumer = next(x["entity"] for x in graph if x.get("entity", {}).get("id") == "skill:consumer")
    assert consumer["properties"]["runtime"]["inputs"] == ["artifact:report"]
    assert any(x.get("relation", {}).get("relation") == "precedes" for x in graph)


def test_import_writes_each_entity_id_once_and_manifest_counts_unique_entities(tmp_path):
    skills = [
        {"id": "one", "source_dir": str(tmp_path), "entrypoints": [], "outputs": ["artifact:report"], "enabled": False},
        {"id": "two", "source_dir": str(tmp_path), "entrypoints": [], "outputs": ["artifact:report"], "enabled": False},
    ]
    cache = Path(receive_bundle(bundle(tmp_path, skills=skills), tmp_path)["output_dir"])
    graph = read_graph(cache)
    entity_ids = [record["entity"]["id"] for record in graph if "entity" in record]
    manifest = json.loads((cache / "cache-manifest.json").read_text(encoding="utf-8"))
    assert len(entity_ids) == len(set(entity_ids))
    assert manifest["entity_count"] == len(entity_ids)


def test_import_reads_explicit_capabilities_from_device_knowledge(tmp_path):
    source = bundle(tmp_path)
    (source / "DeviceKnowledge" / "platform.yaml").write_text(
        "capabilities:\n  - id: capability:liquid-transfer\n", encoding="utf-8"
    )
    cache = Path(receive_bundle(source, tmp_path)["output_dir"])
    suite = next(x["entity"] for x in read_graph(cache) if x.get("entity", {}).get("type") == "SkillSuite")
    assert suite["properties"]["available_capabilities"] == ["capability:liquid-transfer"]


def test_import_uses_skill_capability_contract_when_no_device_file_exists(tmp_path):
    cache = Path(receive_bundle(bundle(tmp_path, skills=[{
        "id": "liquid", "source_dir": str(tmp_path), "entrypoints": [], "outputs": [],
        "required_capabilities": ["capability:liquid-transfer"], "enabled": False,
    }]), tmp_path)["output_dir"])
    suite = next(x["entity"] for x in read_graph(cache) if x.get("entity", {}).get("type") == "SkillSuite")
    assert suite["properties"]["available_capabilities"] == ["capability:liquid-transfer"]
