import json
import shutil
from pathlib import Path

import pytest

import labontology
from labontology import discover_skill_roots, ensure_workspace_cache, main


def _write_skill(root: Path, name: str, description: str = "Do one laboratory check.") -> Path:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill


def _graph_skill_ids(cache: Path) -> set[str]:
    return {
        record["entity"]["id"]
        for record in (json.loads(line) for line in (cache / "ontology.jsonl").read_text(encoding="utf-8").splitlines())
        if record.get("entity", {}).get("type") == "Skill"
    }


def test_first_bootstrap_discovers_workers_and_creates_one_cache_without_backup(tmp_path: Path):
    skill_root = tmp_path / "skills"
    labontology = _write_skill(skill_root, "labontology", "Supervise laboratory workflows.")
    worker_a = _write_skill(skill_root, "worker-a")
    worker_b = _write_skill(skill_root, "worker-b")
    before = {path: path.read_bytes() for path in (labontology / "SKILL.md", worker_a / "SKILL.md", worker_b / "SKILL.md")}

    result = ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    cache = Path(result["cache_dir"])

    assert result["reused"] is False
    assert cache.is_dir()
    assert _graph_skill_ids(cache) == {"skill:worker-a", "skill:worker-b"}
    assert not (cache / ".backup").exists()
    assert {path: path.read_bytes() for path in before} == before


def test_second_bootstrap_reuses_a_current_cache(tmp_path: Path):
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "worker-a")

    first = ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    second = ensure_workspace_cache(tmp_path, skill_roots=[skill_root])

    assert second["cache_dir"] == first["cache_dir"]
    assert second["reused"] is True
    assert second["synchronized"] is False


def test_bootstrap_refreshes_when_a_worker_is_added_and_keeps_latest_backup(tmp_path: Path):
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "worker-a")
    ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    _write_skill(skill_root, "worker-b")

    result = ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    cache = Path(result["cache_dir"])

    assert result["reused"] is False
    assert result["synchronized"] is True
    assert _graph_skill_ids(cache) == {"skill:worker-a", "skill:worker-b"}
    assert (cache / ".backup" / "ontology.jsonl").is_file()


def test_bootstrap_refreshes_when_a_worker_changes(tmp_path: Path):
    skill_root = tmp_path / "skills"
    worker = _write_skill(skill_root, "worker-a", "old description")
    ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    (worker / "SKILL.md").write_text(
        "---\nname: worker-a\ndescription: new description\n---\n\n# worker-a\n",
        encoding="utf-8",
    )

    result = ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    cache = Path(result["cache_dir"])

    assert result["synchronized"] is True
    assert (cache / ".backup" / "ontology.jsonl").is_file()


def test_bootstrap_refreshes_when_a_worker_is_removed(tmp_path: Path):
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "worker-a")
    worker_b = _write_skill(skill_root, "worker-b")
    ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    for path in worker_b.rglob("*"):
        if path.is_file():
            path.unlink()
    worker_b.rmdir()

    result = ensure_workspace_cache(tmp_path, skill_roots=[skill_root])
    assert result["synchronized"] is True
    assert _graph_skill_ids(Path(result["cache_dir"])) == {"skill:worker-a"}


def test_bootstrap_merges_workers_from_multiple_visible_roots(tmp_path: Path):
    first_root = tmp_path / "first" / "skills"
    second_root = tmp_path / "second" / "skills"
    _write_skill(first_root, "worker-a")
    _write_skill(second_root, "worker-b")

    result = ensure_workspace_cache(tmp_path, skill_roots=[first_root, second_root])

    assert set(result["roots"]) == {str(first_root.resolve()), str(second_root.resolve())}
    assert _graph_skill_ids(Path(result["cache_dir"])) == {"skill:worker-a", "skill:worker-b"}


def test_multi_root_bootstrap_rolls_back_when_a_later_root_fails(tmp_path: Path, monkeypatch):
    first_root = tmp_path / "first" / "skills"
    second_root = tmp_path / "second" / "skills"
    _write_skill(first_root, "worker-a")
    _write_skill(second_root, "worker-b")
    original_sync = labontology.sync_workspace
    calls = 0

    def fail_on_second_root(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("synthetic second-root failure")
        return original_sync(*args, **kwargs)

    monkeypatch.setattr(labontology, "sync_workspace", fail_on_second_root)

    with pytest.raises(ValueError, match="synthetic second-root failure"):
        ensure_workspace_cache(tmp_path, skill_roots=[first_root, second_root])

    assert not (tmp_path / "labontology_workspace_cache").exists()


def test_automatic_bootstrap_does_not_silently_ignore_a_missing_cached_root(tmp_path: Path, monkeypatch):
    first_root = tmp_path / "first" / "skills"
    second_root = tmp_path / "second" / "skills"
    _write_skill(first_root, "worker-a")
    _write_skill(second_root, "worker-b")
    ensure_workspace_cache(tmp_path, skill_roots=[first_root, second_root])
    shutil.rmtree(second_root)
    monkeypatch.setattr(labontology, "discover_skill_roots", lambda **_: [first_root])

    with pytest.raises(ValueError, match="Previously cached Skill root is unavailable"):
        ensure_workspace_cache(tmp_path)


def test_automatic_bootstrap_prefers_the_labontology_sibling_root(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    anchor_root = tmp_path / "installed" / "skills"
    other_root = workspace / ".codex" / "skills"
    _write_skill(anchor_root, "labontology", "Supervise laboratory workflows.")
    _write_skill(anchor_root, "worker-a")
    _write_skill(other_root, "unrelated-worker")
    monkeypatch.setattr(labontology, "_default_skill_dir", lambda: anchor_root / "labontology")

    result = ensure_workspace_cache(workspace)

    assert result["roots"] == [str(anchor_root.resolve())]
    assert _graph_skill_ids(Path(result["cache_dir"])) == {"skill:worker-a"}


def test_bootstrap_cli_uses_discovery_without_skill_path_flags(tmp_path: Path, monkeypatch, capsys):
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "worker-a")
    monkeypatch.setattr("labontology.discover_skill_roots", lambda **_: [skill_root])

    assert main(["bootstrap", "--workspace", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["reused"] is False
    assert result["roots"] == [str(skill_root.resolve())]


def test_bootstrap_from_project_skill_directory_uses_project_root_as_workspace(
    tmp_path: Path, monkeypatch, capsys
):
    project = tmp_path / "project"
    skill_root = project / ".claude" / "skills"
    _write_skill(skill_root, "labontology", "Supervise laboratory workflows.")
    _write_skill(skill_root, "worker-a")
    monkeypatch.setattr(labontology, "_default_skill_dir", lambda: skill_root / "labontology")
    monkeypatch.chdir(skill_root / "labontology")

    assert main(["bootstrap"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["cache_dir"] == str((project / "labontology_workspace_cache").resolve())
    assert not (skill_root / "labontology" / "labontology_workspace_cache").exists()


def test_bootstrap_without_visible_skill_root_fails_without_creating_cache(tmp_path: Path):
    with pytest.raises(ValueError, match="No visible standard Skill root"):
        ensure_workspace_cache(tmp_path, skill_roots=[])

    assert not (tmp_path / "labontology_workspace_cache").exists()


def test_discover_skill_roots_is_stable_and_skips_empty_directories(tmp_path: Path):
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "worker-a")
    empty = tmp_path / "empty"
    empty.mkdir()

    roots = discover_skill_roots(skill_dir=skill_root / "labontology", workspace=tmp_path)

    assert roots[0] == skill_root
    assert len(roots) == len(set(roots))
    assert empty not in roots


def test_discovery_does_not_scan_unrelated_ancestor_skill_roots(tmp_path: Path):
    workspace = tmp_path / "project"
    local_root = workspace / ".agent" / "skills"
    _write_skill(local_root, "worker-a")
    unrelated_root = tmp_path / ".codex" / "skills"
    _write_skill(unrelated_root, "unrelated-worker")

    roots = discover_skill_roots(
        skill_dir=local_root / "labontology",
        workspace=workspace,
    )

    assert local_root in roots
    assert unrelated_root not in roots


def test_configured_skill_roots_take_precedence_over_automatic_roots(tmp_path: Path, monkeypatch):
    automatic_root = tmp_path / ".agents" / "skills"
    configured_root = tmp_path / "configured-skills"
    _write_skill(automatic_root, "automatic-worker")
    _write_skill(configured_root, "configured-worker")
    monkeypatch.setenv("LABONTOLOGY_SKILL_ROOTS", str(configured_root))

    roots = discover_skill_roots(
        skill_dir=automatic_root / "labontology",
        workspace=tmp_path,
    )

    assert roots == [configured_root.resolve()]
