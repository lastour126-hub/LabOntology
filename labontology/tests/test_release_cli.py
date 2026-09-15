import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI = PROJECT_ROOT / "labontology" / "scripts" / "labontology.py"


def run_cli(*args: str, check: bool = True, input: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=input,
        check=check,
    )


def make_skill_root(tmp_path: Path) -> Path:
    skill_root = tmp_path / "demo-skill"
    skill_root.mkdir()
    (skill_root / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Inspect a local record.\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    return skill_root


def import_demo_cache(tmp_path: Path) -> Path:
    result = json.loads(run_cli(
        "import", str(make_skill_root(tmp_path)),
        "--suite-id", "suite:demo", "--workspace", str(tmp_path),
    ).stdout)
    return Path(result["cache_dir"])


def make_process_skill_root(tmp_path: Path, skill_id: str, side_effect_level: str) -> Path:
    skill_root = tmp_path / f"{skill_id}-skill"
    skill_root.mkdir()
    (skill_root / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: Run a local check.\n---\n\n# {skill_id}\n",
        encoding="utf-8",
    )
    (skill_root / "skill.yaml").write_text(
        f"id: {skill_id}\ndescription: Run a local check.\nside_effect_level: {side_effect_level}\n",
        encoding="utf-8",
    )
    scripts = skill_root / "scripts"
    scripts.mkdir()
    (scripts / "check.py").write_text("print('checked')\n", encoding="utf-8")
    return skill_root


def cache_and_mission(tmp_path: Path, skill_id: str, side_effect_level: str) -> tuple[Path, str]:
    result = json.loads(run_cli(
        "import", str(make_process_skill_root(tmp_path, skill_id, side_effect_level)),
        "--suite-id", "suite:decision", "--workspace", str(tmp_path),
    ).stdout)
    cache = Path(result["cache_dir"])
    mission_id = "decision"
    mission_dir = cache / "runs" / mission_id
    mission_dir.mkdir()
    (mission_dir / "state.json").write_text(json.dumps({
        "mission_id": mission_id,
        "status": "awaiting_decision",
        "mode": "agent",
        "goal": "Check safety",
    }), encoding="utf-8")
    return cache, mission_id


def test_import_creates_and_validates_a_cache(tmp_path: Path):
    result = json.loads(run_cli(
        "import", str(make_skill_root(tmp_path)),
        "--suite-id", "suite:demo", "--workspace", str(tmp_path),
    ).stdout)

    assert result["suite_id"] == "suite:demo"
    assert Path(result["cache_dir"]).is_dir()
    assert result["validation"] == {"graphs": 1, "valid": True}


def test_import_reports_only_the_imported_suite_skill_count(tmp_path: Path):
    first = make_skill_root(tmp_path)
    second = tmp_path / "second-skill"
    second.mkdir()
    (second / "SKILL.md").write_text("---\nname: second\n---\n", encoding="utf-8")
    run_cli("import", str(first), "--suite-id", "suite:first", "--workspace", str(tmp_path))

    result = json.loads(run_cli(
        "import", str(second), "--suite-id", "suite:second", "--workspace", str(tmp_path),
    ).stdout)

    assert result["skill_count"] == 1


def test_inspect_reports_cache_summary(tmp_path: Path):
    cache = import_demo_cache(tmp_path)

    result = json.loads(run_cli("inspect", "--cache-dir", str(cache)).stdout)

    assert result["suite_id"] == "suite:demo"
    assert result["skill_count"] == 1
    assert result["source_integrity"]["missing"] == 0


def test_resolve_cache_reuses_matching_valid_cache(tmp_path: Path):
    source = make_skill_root(tmp_path)
    imported = json.loads(run_cli(
        "import", str(source), "--suite-id", "suite:demo", "--workspace", str(tmp_path),
    ).stdout)

    result = json.loads(run_cli(
        "resolve-cache", "--skill-root", str(source), "--workspace", str(tmp_path),
        "--suite-id", "suite:demo",
    ).stdout)

    assert result["cache_dir"] == imported["cache_dir"]
    assert result["suite_id"] == "suite:demo"
    assert result["candidate_count"] == 1


def test_sync_imports_an_unclassified_skill_into_general_suite(tmp_path: Path):
    source = make_skill_root(tmp_path)

    result = json.loads(run_cli(
        "sync", "--skill-root", str(source), "--workspace", str(tmp_path),
    ).stdout)

    assert result["cache_dir"].endswith("labontology_workspace_cache")
    assert result["suite_ids"] == ["suite:general"]


def test_sync_reuses_a_current_explicit_suite_without_rebuilding(tmp_path: Path):
    source = make_skill_root(tmp_path)
    run_cli("import", str(source), "--suite-id", "suite:demo", "--workspace", str(tmp_path))

    result = json.loads(run_cli(
        "sync", "--skill-root", str(source), "--suite-id", "suite:demo", "--workspace", str(tmp_path),
    ).stdout)

    assert result["synchronized"] is False
    assert result["reused"] is True


def test_sync_refreshes_the_existing_suite_for_a_known_root_without_reclassifying_it(tmp_path: Path):
    source = make_skill_root(tmp_path)
    run_cli("import", str(source), "--suite-id", "suite:demo", "--workspace", str(tmp_path))
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: changed\n---\n", encoding="utf-8")

    result = json.loads(run_cli(
        "sync", "--skill-root", str(source), "--workspace", str(tmp_path),
    ).stdout)

    assert result["suite_id"] == "suite:demo"
    assert result["suite_ids"] == ["suite:demo"]


def test_resolve_cache_for_one_suite_ignores_another_suite_stale_sources(tmp_path: Path):
    first = make_skill_root(tmp_path)
    second = tmp_path / "other-skill"
    second.mkdir()
    second_document = second / "SKILL.md"
    second_document.write_text("---\nname: other\n---\n", encoding="utf-8")
    run_cli("import", str(first), "--suite-id", "suite:first", "--workspace", str(tmp_path))
    run_cli("import", str(second), "--suite-id", "suite:second", "--workspace", str(tmp_path))
    second_document.write_text("---\nname: other\ndescription: changed\n---\n", encoding="utf-8")

    result = json.loads(run_cli(
        "resolve-cache", "--skill-root", str(first), "--suite-id", "suite:first", "--workspace", str(tmp_path),
    ).stdout)

    assert result["suite_id"] == "suite:first"
    assert result["source_integrity"]["changed"] == 0


def test_run_creates_mission_and_returns_context(tmp_path: Path):
    cache = import_demo_cache(tmp_path)

    result = json.loads(run_cli(
        "run", "--cache-dir", str(cache), "--goal", "核实条件",
    ).stdout)

    assert result["mission_id"]
    assert result["mission"]["status"] == "awaiting_decision"


def test_run_preserves_task_spreadsheet_as_a_mission_artifact(tmp_path: Path):
    cache = import_demo_cache(tmp_path)
    spreadsheet = tmp_path / "chemical_space.xlsx"
    spreadsheet.write_bytes(b"task input")

    result = json.loads(run_cli(
        "run", "--cache-dir", str(cache), "--goal", "plan reaction",
        "--input-artifact", f"chemical-space={spreadsheet}",
    ).stdout)

    assert result["mission"]["artifacts"]["chemical-space"] == str(spreadsheet.resolve())


def test_resume_is_available_from_release_entrypoint(tmp_path: Path):
    cache = import_demo_cache(tmp_path)
    mission_id = json.loads(run_cli(
        "run", "--cache-dir", str(cache), "--goal", "resume me",
    ).stdout)["mission_id"]

    result = json.loads(run_cli(
        "resume", "--cache-dir", str(cache), "--mission-id", mission_id,
    ).stdout)

    assert result["mission"]["mission_id"] == mission_id


def test_describe_skill_returns_full_details_only_for_selected_skill(tmp_path: Path):
    cache = import_demo_cache(tmp_path)

    result = json.loads(run_cli(
        "describe-skill", "--cache-dir", str(cache), "--skill-id", "demo", "--suite-id", "suite:demo",
    ).stdout)

    assert result["id"] == "demo"
    assert result["suite_id"] == "suite:demo"
    assert "instruction_source" in result


def test_missions_lists_existing_missions_and_matches_goal_text(tmp_path: Path):
    cache = import_demo_cache(tmp_path)
    run_cli("run", "--cache-dir", str(cache), "--mission-id", "yesterday", "--goal", "continue reaction")

    result = json.loads(run_cli("missions", "--cache-dir", str(cache), "--query", "reaction").stdout)

    assert result["missions"] == [{"mission_id": "yesterday", "goal": "continue reaction", "status": "awaiting_decision"}]


def test_status_reads_mission_created_by_run(tmp_path: Path):
    cache = import_demo_cache(tmp_path)
    mission_id = json.loads(run_cli(
        "run", "--cache-dir", str(cache), "--goal", "核实条件",
    ).stdout)["mission_id"]

    result = json.loads(run_cli(
        "status", "--cache-dir", str(cache), "--mission-id", mission_id,
    ).stdout)

    assert result["mission_id"] == mission_id


def test_decide_rejects_significant_device_action(tmp_path: Path):
    cache, mission_id = cache_and_mission(tmp_path, "device", "significant")

    completed = run_cli(
        "decide", "--cache-dir", str(cache), "--mission-id", mission_id,
        "--skill-id", "device", "--reason", "run device", check=False,
    )

    assert completed.returncode != 0
    assert "significant" in completed.stderr.lower()


def test_decide_requires_explicit_routine_confirmation(tmp_path: Path):
    cache, mission_id = cache_and_mission(tmp_path, "routine", "read_only")

    completed = run_cli(
        "decide", "--cache-dir", str(cache), "--mission-id", mission_id,
        "--skill-id", "routine", "--reason", "read source", input="n\n", check=False,
    )

    assert completed.returncode != 0
    assert "cancelled" in completed.stderr.lower()


def test_decide_executes_confirmed_routine_action(tmp_path: Path):
    cache, mission_id = cache_and_mission(tmp_path, "routine", "read_only")

    result = json.loads(run_cli(
        "decide", "--cache-dir", str(cache), "--mission-id", mission_id,
        "--skill-id", "routine", "--reason", "read source", input="yes\n",
    ).stdout)

    assert result["mission"]["observations"][-1]["status"] == "succeeded"


def test_decide_selects_a_skill_from_an_explicit_suite_in_a_unified_cache(tmp_path: Path):
    cache, mission_id = cache_and_mission(tmp_path, "routine", "read_only")
    run_cli(
        "import", str(make_process_skill_root(tmp_path, "other", "read_only")),
        "--suite-id", "suite:other", "--workspace", str(tmp_path),
    )

    result = json.loads(run_cli(
        "decide", "--cache-dir", str(cache), "--mission-id", mission_id,
        "--skill-id", "routine", "--suite-id", "suite:decision", "--reason", "read source", input="yes\n",
    ).stdout)

    assert result["mission"]["observations"][-1]["status"] == "succeeded"


def test_fdu_quick_start_imports_and_starts_a_read_only_mission(tmp_path: Path):
    imported = json.loads(run_cli(
        "import", str(PROJECT_ROOT / "FduSkills"),
        "--suite-id", "suite:fdu-quickstart", "--workspace", str(tmp_path),
    ).stdout)

    result = json.loads(run_cli(
        "run", "--cache-dir", imported["cache_dir"],
        "--goal", "检查实验步骤所需资源是否齐全",
    ).stdout)

    assert result["mission"]["status"] == "awaiting_decision"


def test_release_skill_runs_without_repository_siblings(tmp_path: Path):
    published = tmp_path / "published"
    shutil.copytree(PROJECT_ROOT / "labontology", published)
    source = make_skill_root(tmp_path)
    command = [sys.executable, str(published / "scripts" / "labontology.py")]
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}

    imported = subprocess.run(
        [*command, "import", str(source), "--suite-id", "suite:isolated", "--workspace", str(tmp_path)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    cache = Path(json.loads(imported.stdout)["cache_dir"])
    started = subprocess.run(
        [*command, "run", "--cache-dir", str(cache), "--goal", "inspect safely"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(started.stdout)["mission"]["status"] == "awaiting_decision"


def test_public_entrypoint_emits_utf8_json_for_chinese_goal(tmp_path: Path):
    cache = import_demo_cache(tmp_path)

    completed = subprocess.run(
        [sys.executable, str(CLI), "run", "--cache-dir", str(cache),
         "--mission-id", "utf8", "--goal", "核实实验条件"],
        capture_output=True,
        check=True,
    )

    assert json.loads(completed.stdout.decode("utf-8"))["mission"]["goal"] == "核实实验条件"
