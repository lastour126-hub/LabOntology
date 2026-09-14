import json
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


def test_inspect_reports_cache_summary(tmp_path: Path):
    cache = import_demo_cache(tmp_path)

    result = json.loads(run_cli("inspect", "--cache-dir", str(cache)).stdout)

    assert result["suite_id"] == "suite:demo"
    assert result["skill_count"] == 1
    assert result["source_integrity"]["missing"] == 0


def test_run_creates_mission_and_returns_context(tmp_path: Path):
    cache = import_demo_cache(tmp_path)

    result = json.loads(run_cli(
        "run", "--cache-dir", str(cache), "--goal", "核实条件",
    ).stdout)

    assert result["mission_id"]
    assert result["mission"]["status"] == "awaiting_decision"


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
