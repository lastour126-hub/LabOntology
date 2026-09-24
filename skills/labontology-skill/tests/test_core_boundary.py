from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _published_skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_release_core_never_imports_archived_skills():
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "scripts" / "core").rglob("*.py")
    )

    assert "archived_skills" not in source
    assert "labontology-creator" not in source
    assert "labontology-run" not in source


def test_only_labontology_is_a_published_skill():
    root = _project_root()

    assert (_published_skill_root() / "SKILL.md").is_file()
    assert not (root / "labontology-creator").exists()
    assert not (root / "labontology-run").exists()
