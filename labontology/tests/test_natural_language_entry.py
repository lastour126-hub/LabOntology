from pathlib import Path


def test_skill_routes_natural_language_tasks_without_exposing_commands():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "## Conversation-first workflow" in skill
    assert "## Internal command routing" in skill
    assert "## Safety boundary" in skill
    assert "Do not ask the user to choose a command" in skill
    assert "prepare or plan an experiment" in skill
    assert "check readiness or progress" in skill
    assert "maintain the workflow library" in skill
    assert "request an action" in skill
