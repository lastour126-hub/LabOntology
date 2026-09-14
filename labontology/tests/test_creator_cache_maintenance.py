import json
from pathlib import Path

from core.creator.intake import maintain_cache, receive_bundle


def make_cache(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "skills.json").write_text(json.dumps({
        "schema": "labontology.skill-bundle.v1", "suite_id": "suite:maintained",
        "skills": [{"id": "reader", "source_dir": str(tmp_path), "entrypoints": [],
                    "knowledge_files": [], "outputs": [], "enabled": False}],
        "device_knowledge": [], "workflows": []}), encoding="utf-8")
    (bundle / "DeviceKnowledge").mkdir()
    (bundle / "Workflow").mkdir()
    return Path(receive_bundle(bundle, tmp_path)["output_dir"])


def test_maintenance_records_device_and_workflow_sources_in_one_index(tmp_path):
    cache = make_cache(tmp_path)
    device = tmp_path / "centrifuge.yaml"
    workflow = tmp_path / "sample-prep.md"
    device.write_text("speed: 1000", encoding="utf-8")
    workflow.write_text("step order", encoding="utf-8")
    maintain_cache(cache, device, kind="device")
    maintain_cache(cache, workflow, kind="workflow")
    index = json.loads((cache / "source-index.json").read_text(encoding="utf-8"))
    assert {role for item in index["sources"] if item["path"] in {str(device.resolve()), str(workflow.resolve())} for role in item["roles"]} == {"device_knowledge", "workflow"}
    assert not (cache / "DeviceKnowledge").exists()
    assert not (cache / "Workflow").exists()


def test_maintenance_replaces_same_external_source_record(tmp_path):
    cache = make_cache(tmp_path)
    source = tmp_path / "rule.md"
    source.write_text("v1", encoding="utf-8")
    maintain_cache(cache, source, kind="knowledge", skill_id="reader")
    source.write_text("v2", encoding="utf-8")
    maintain_cache(cache, source, kind="knowledge", skill_id="reader")
    index = json.loads((cache / "source-index.json").read_text(encoding="utf-8"))
    records = [item for item in index["sources"] if item["path"] == str(source.resolve())]
    assert len(records) == 1
    assert records[0]["sha256"]


def test_maintenance_updates_cache_manifest_timestamp(tmp_path):
    cache = make_cache(tmp_path)
    before = json.loads((cache / "cache-manifest.json").read_text(encoding="utf-8"))["updated_at"]
    source = tmp_path / "rule.md"
    source.write_text("v1", encoding="utf-8")
    maintain_cache(cache, source, kind="knowledge")
    manifest = json.loads((cache / "cache-manifest.json").read_text(encoding="utf-8"))
    assert manifest["updated_at"] >= before

