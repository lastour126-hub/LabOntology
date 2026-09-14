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
