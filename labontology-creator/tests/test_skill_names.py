from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]


def test_public_skill_names_are_creator_and_run():
    creator_root = PROJECT_ROOT / "labontology-creator"
    run_root = PROJECT_ROOT / "labontology-run"

    assert creator_root.is_dir()
    assert run_root.is_dir()
    assert "name: labontology-creator" in (creator_root / "SKILL.md").read_text(encoding="utf-8")
    assert "name: labontology-run" in (run_root / "SKILL.md").read_text(encoding="utf-8")
