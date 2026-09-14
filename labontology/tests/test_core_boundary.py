from pathlib import Path


def test_release_core_never_imports_archived_skills():
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "scripts" / "core").rglob("*.py")
    )

    assert "old_skills" not in source
    assert "labontology-creator" not in source
    assert "labontology-run" not in source


def test_only_labontology_is_a_published_skill():
    root = Path(__file__).resolve().parents[2]

    assert (root / "labontology" / "SKILL.md").is_file()
    assert not (root / "labontology-creator").exists()
    assert not (root / "labontology-run").exists()
    assert (root / "old_skills" / "labontology-creator" / "SKILL.md").is_file()
    assert (root / "old_skills" / "labontology-run" / "SKILL.md").is_file()
