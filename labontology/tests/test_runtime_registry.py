from core.runtime.registry import Registry


def test_registry_loads_suite_skills_from_data(tmp_path):
    registry_path = tmp_path / "registry.yaml"
    suite_dir = tmp_path / "fdu"
    suite_dir.mkdir()
    registry_path.write_text(
        """version: '0.1'\nsuites:\n  - id: suite:test\n    name: Test Suite\n    skills_file: fdu/skills.yaml\n""",
        encoding="utf-8",
    )
    (suite_dir / "skills.yaml").write_text(
        """skills:\n  - id: skill:test\n    command: [python, -c, 'print(1)']\n""",
        encoding="utf-8",
    )

    registry = Registry.load(registry_path)
    suite = registry.suite("suite:test")

    assert suite.skills["skill:test"].id == "skill:test"

