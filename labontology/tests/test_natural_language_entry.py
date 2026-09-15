from pathlib import Path


def test_skill_routes_natural_language_tasks_without_exposing_commands():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    normalized = skill.lower()

    assert "## Conversation-first workflow" in skill
    assert "## Internal command routing" in skill
    assert "## Safety boundary" in skill
    assert "Do not ask the user to choose a command" in skill
    assert "prepare or plan an experiment" in normalized
    assert "check readiness or progress" in normalized
    assert "maintain the workflow library" in normalized
    assert "request an action" in normalized


def test_readme_explains_conversation_first_use():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "## Use it in conversation" in readme
    assert "The Agent selects the workflow internally" in readme


def test_skill_requires_cache_resolution_before_importing():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "resolve-cache" in skill
    assert "synchronize the workspace Skill root" in skill
    assert "one workspace cache" in skill
    assert "A task data file is not a reason to rebuild the workflow-library cache" in skill


def test_skill_declares_one_workspace_graph_with_explicit_suites():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "one workspace cache" in skill
    assert "SkillSuite" in skill
    assert "synchronize" in skill
    assert "task data file" in skill


def test_skill_defines_laboratory_language_for_common_user_states():
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    assert "## User-facing response contract" in skill
    assert "**Ready:**" in skill
    assert "**Missing condition:**" in skill
    assert "**Waiting for approval:**" in skill
    assert "**Paused task:**" in skill
    assert "Do not expose raw tracebacks" in skill


def test_readme_shows_user_facing_experiment_language():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    assert "Responses are written for experiment users" in readme
    assert "实验流程库需要更新" in readme
