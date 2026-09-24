import hashlib
import json
from pathlib import Path

import pytest

from core.creator.backup import backup_active_graph, restore_active_graph
from core.creator.intake import receive_bundle


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


def test_backup_records_hashes_and_restores_the_active_graph(tmp_path):
    cache = Path(receive_bundle(_bundle(tmp_path), tmp_path)["output_dir"])
    original = {name: (cache / name).read_bytes()
                for name in ("ontology.jsonl", "source-index.json", "cache-manifest.json")}

    result = backup_active_graph(cache, "before maintenance")

    backup = cache / ".backup"
    assert {path.name for path in backup.iterdir()} == set(original)
    assert result["reason"] == "before maintenance"
    assert result["files"]["ontology.jsonl"]["sha256"] == hashlib.sha256(original["ontology.jsonl"]).hexdigest()

    (cache / "ontology.jsonl").write_text("broken\n", encoding="utf-8")
    restored = restore_active_graph(cache)
    assert restored["restored"] == sorted(original)
    assert (cache / "ontology.jsonl").read_bytes() == original["ontology.jsonl"]


def test_restore_rejects_an_incomplete_backup_without_touching_active_graph(tmp_path):
    cache = Path(receive_bundle(_bundle(tmp_path), tmp_path)["output_dir"])
    backup_active_graph(cache, "test")
    (cache / "ontology.jsonl").write_text("still active\n", encoding="utf-8")
    (cache / ".backup" / "source-index.json").unlink()

    with pytest.raises(ValueError, match="incomplete backup"):
        restore_active_graph(cache)

    assert (cache / "ontology.jsonl").read_text(encoding="utf-8") == "still active\n"


def test_compact_cache_replacement_keeps_the_latest_backup(tmp_path):
    cache = Path(receive_bundle(_bundle(tmp_path), tmp_path)["output_dir"])
    previous_graph = (cache / "ontology.jsonl").read_bytes()

    receive_bundle(_bundle(tmp_path / "refresh"), tmp_path)

    assert (cache / ".backup" / "ontology.jsonl").read_bytes() == previous_graph
    assert {path.name for path in (cache / ".backup").iterdir()} == {
        "ontology.jsonl", "source-index.json", "cache-manifest.json",
    }


def test_compact_cache_swap_failure_restores_the_previous_cache(tmp_path, monkeypatch):
    cache = Path(receive_bundle(_bundle(tmp_path), tmp_path)["output_dir"])
    previous_graph = (cache / "ontology.jsonl").read_bytes()
    original_replace = Path.replace

    def fail_graph_swap(self, target):
        if self.name == f".{cache.name}-graph-build" and Path(target).resolve() == cache.resolve():
            raise OSError("simulated cache swap failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_graph_swap)

    with pytest.raises(OSError, match="simulated cache swap failure"):
        receive_bundle(_bundle(tmp_path / "refresh"), tmp_path)

    assert cache.is_dir()
    assert (cache / "ontology.jsonl").read_bytes() == previous_graph
